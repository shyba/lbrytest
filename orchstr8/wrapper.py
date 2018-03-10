from __future__ import print_function

import json
import os
import signal
import shutil
import zipfile
import tempfile
import logging

import requests
from twisted.internet import reactor, defer, utils
from twisted.internet.protocol import ProcessProtocol

from lbrynet import conf as lbry_conf
from lbrynet.core.call_later_manager import CallLaterManager
from lbrynet.daemon.DaemonServer import DaemonServer as LbryDaemonServer
from lbryumserver.main import start_server, stop_server, create_config


class LbryServiceStack:

    def __init__(self, verbose=False):
        defer.Deferred.debug = verbose
        if verbose:
            logging.getLogger('lbrynet').setLevel(logging.INFO)
            logging.getLogger('lbryum').setLevel(logging.INFO)
            logging.getLogger('lbryumserver').setLevel(logging.INFO)
        else:
            logging.getLogger('lbrynet').setLevel(logging.ERROR)
            logging.getLogger('lbryum').setLevel(logging.ERROR)
            logging.getLogger('lbryumserver').setLevel(logging.ERROR)
        self.lbrycrd = Lbrycrd(verbose=verbose)
        self.lbryumserver = LbryumServer(self.lbrycrd)
        self.lbry = Lbry()

    @defer.inlineCallbacks
    def startup(self, before_lbrycrd_start=None, after_lbrycrd_start=None):
        CallLaterManager.setup(reactor.callLater)
        self.lbrycrd.setup()
        if before_lbrycrd_start:
            yield defer.maybeDeferred(before_lbrycrd_start)
        yield self.lbrycrd.start()
        if after_lbrycrd_start:
            yield defer.maybeDeferred(after_lbrycrd_start)
        else:
            # lbry.start() will never return unless there
            # are some blocks generated first
            yield self.lbrycrd.generate(110)
        yield self.lbryumserver.start()
        yield self.lbry.start()

    @defer.inlineCallbacks
    def shutdown(self, cleanup=True):
        try:
            yield self.lbry.stop(cleanup=cleanup)
        except Exception as e:
            print(e)

        try:
            CallLaterManager.stop()
        except Exception as e:
            print(e)

        try:
            yield self.lbryumserver.stop(cleanup=cleanup)
        except Exception as e:
            print(e)

        try:
            yield self.lbrycrd.stop(cleanup=cleanup)
        except Exception as e:
            print(e)


class MocAnalyticsManager:
    def __init__(self):
        self.is_started = True

    def shutdown(self):
        pass

    def send_claim_action(self, action):
        pass


class Lbry:

    def __init__(self, verbose=False):
        self.verbose = verbose
        self.data_path = None
        self.wallet_directory = None
        self.download_directory = None
        self.server = LbryDaemonServer(MocAnalyticsManager())

    @property
    def daemon(self):
        assert self.server._daemon is not None, "Lbry daemon has not been started."
        return self.server._daemon

    @property
    def session(self):
        return self.daemon.session

    @property
    def wallet(self):
        return self.session.wallet

    def stratum_command(self, method, *args):
        network = self.wallet.network
        return network.synchronous_get([method, list(args)])

    def start(self):
        self.data_path = tempfile.mkdtemp()

        self.wallet_directory = os.path.join(self.data_path, 'lbryum')
        self.download_directory = os.path.join(self.data_path, 'Downloads')

        os.mkdir(self.wallet_directory)
        os.mkdir(self.download_directory)

        with open(os.path.join(self.wallet_directory, 'regtest_headers'), 'w'):
            pass

        lbry_conf.settings = None
        lbry_conf.initialize_settings(load_conf_file=False)
        lbry_conf.settings['data_dir'] = os.path.join(self.data_path, 'lbrynet')
        lbry_conf.settings['lbryum_wallet_dir'] = self.wallet_directory
        lbry_conf.settings['download_directory'] = self.download_directory
        lbry_conf.settings['use_upnp'] = False
        lbry_conf.settings['blockchain_name'] = 'lbrycrd_regtest'
        lbry_conf.settings['lbryum_servers'] = [('localhost', 50001)]
        lbry_conf.settings['known_dht_nodes'] = []
        lbry_conf.settings.load_conf_file_settings()

        return self.server.start(use_auth=False)

    @defer.inlineCallbacks
    def stop(self, cleanup=True):
        try:
            yield self.daemon.exchange_rate_manager.stop()
            yield self.daemon._shutdown()
            yield self.server.server_port.stopListening()
        finally:
            if cleanup:
                self.cleanup()

    def cleanup(self):
        shutil.rmtree(self.data_path, ignore_errors=True)


class LbryumServer:

    def __init__(self, lbrycrd):
        self.lbrycrd = lbrycrd
        self.data_path = None
        self.transports = []

    @property
    def lbryum_conf(self):
        return os.path.join(self.data_path, 'lbryum.conf')

    def start(self):
        self.data_path = tempfile.mkdtemp()
        with open(self.lbryum_conf, 'w') as conf:
            conf.write(
                '[network]\n'
                'type=lbrycrd_regtest\n'
                '[server]\n'
                'logfile={}\n'
                'stratum_tcp_port=50001\n'
                'stratum_http_port=\n'
                'stratum_tcp_ssl_port=\n'
                'stratum_http_ssl_port=\n'
                '[leveldb]\n'
                'path={}\n'
                .format(
                   os.path.join(self.data_path, 'lbryum.log'),
                   os.path.join(self.data_path, 'lbryum_db')
                )
            )
        config = create_config(
            filename=self.lbryum_conf,
            lbrycrdd_dir=self.lbrycrd.data_path
        )
        self.transports = start_server(config, setup_logging=False)
        assert len(self.transports) == 1, "Should have exactly one transport server, startum tcp."
        return self.transports[0].started

    @defer.inlineCallbacks
    def stop(self, cleanup=True):
        try:
            stop_server()
            yield self.transports[0].stopped
        finally:
            if cleanup:
                self.cleanup()

    def cleanup(self):
        shutil.rmtree(self.data_path, ignore_errors=True)


class LbrycrdProcess(ProcessProtocol):

    IGNORE_OUTPUT = [
        'keypool keep',
        'keypool reserve',
        'keypool return',
    ]

    def __init__(self, verbose=False):
        self.ready = defer.Deferred()
        self.stopped = defer.Deferred()
        self.verbose = verbose

    def _print_output(self, data):
        if self.verbose and not any(ignore in data for ignore in self.IGNORE_OUTPUT):
            print(data)

    def outReceived(self, data):
        self._print_output(data)
        called = self.ready.called
        if not called and 'Error:' in data:
            self.ready.callback(False)
        if not called and 'Done loading' in data:
            self.ready.callback(True)

    def errReceived(self, data):
        self.verbose and print(data)
        if not self.ready.called:
            self.ready.callback(False)

    def processEnded(self, reason):
        if not self.stopped.called:
            self.stopped.callback(True)

    def stop(self):
        if self.transport.pid:
            os.kill(self.transport.pid, signal.SIGTERM)
            return self.stopped
        return defer.succeed(True)


class Lbrycrd:

    def __init__(self, parent_path=None, bin_path=None, verbose=False):
        self.parent_data_path = parent_path
        self.data_path = None
        self.project_dir = os.path.dirname(os.path.dirname(__file__))
        self.lbrycrd_dir = bin_path or os.path.join(self.project_dir, 'bin')
        self.lbrycrd_zip = 'lbrycrd-linux.zip'
        self.zip_path = os.path.join(self.lbrycrd_dir, self.lbrycrd_zip)
        self.lbrycrd_cli_path = os.path.join(self.lbrycrd_dir, 'lbrycrd-cli')
        self.lbrycrdd_path = os.path.join(self.lbrycrd_dir, 'lbrycrdd')
        self.process = None
        self.verbose = verbose

    @property
    def exists(self):
        return (
            os.path.exists(self.lbrycrdd_path) and
            os.path.exists(self.lbrycrd_cli_path)
        )

    @property
    def latest_release_url(self):
        r = requests.get('https://api.github.com/repos/lbryio/lbrycrd/releases/latest')
        d = r.json()
        for asset in d['assets']:
            if self.lbrycrd_zip in asset['browser_download_url']:
                return asset['browser_download_url']

    def download(self):
        if not os.path.exists(self.lbrycrd_dir):
            os.mkdir(self.lbrycrd_dir)
        r = requests.get(self.latest_release_url, stream=True)
        with open(self.zip_path, 'wb') as f:
            shutil.copyfileobj(r.raw, f)
        with zipfile.ZipFile(self.zip_path) as zf:
            zf.extractall(self.lbrycrd_dir)
        # zipfile bug https://bugs.python.org/issue15795
        os.chmod(self.lbrycrd_cli_path, 0o755)
        os.chmod(self.lbrycrdd_path, 0o755)
        return True

    def ensure(self):
        return self.exists or self.download()

    @property
    def lbrycrd_conf(self):
        return os.path.join(self.data_path, 'lbrycrd.conf')

    def setup(self):
        self.ensure()
        self.data_path = tempfile.mkdtemp()
        with open(self.lbrycrd_conf, 'w') as conf:
            conf.write(
                'rpcuser=rpcuser\n'
                'rpcpassword=rpcpassword\n'
            )

    @defer.inlineCallbacks
    def start(self):
        self.process = LbrycrdProcess(self.verbose)
        reactor.spawnProcess(
            self.process, self.lbrycrdd_path, [
                self.lbrycrdd_path,
                '-datadir={}'.format(self.data_path),
                '-printtoconsole', '-regtest', '-server', '-txindex'
            ]
        )
        yield self.process.ready

    @defer.inlineCallbacks
    def stop(self, cleanup=True):
        try:
            yield self.process.stop()
        finally:
            if cleanup:
                self.cleanup()

    def cleanup(self):
        shutil.rmtree(self.data_path, ignore_errors=True)

    @defer.inlineCallbacks
    def _cli_cmnd(self, *args):
        cmnd_args = [
            '-datadir={}'.format(self.data_path), '-regtest',
        ] + list(args)
        self.verbose and print('{} {}'.format(
            self.lbrycrd_cli_path, ' '.join(cmnd_args)
        ))
        out, err, value = yield utils.getProcessOutputAndValue(
            self.lbrycrd_cli_path, cmnd_args
        )
        self.verbose and print(out)
        if err:
            print(err)
        defer.returnValue((out, err, value))

    @defer.inlineCallbacks
    def generate(self, blocks):
        """ returns a list of generated block hashes """
        out, error, code = yield self._cli_cmnd('generate', str(blocks))
        if error:
            defer.fail((out, code))
        else:
            defer.returnValue(json.loads(out))

    @defer.inlineCallbacks
    def sendtoaddress(self, address, credits):
        """ Returns the transaction id. """
        out, error, code = yield self._cli_cmnd('sendtoaddress', address, str(credits))
        defer.returnValue(out.strip())

    @defer.inlineCallbacks
    def abandonclaim(self, txid, address, amount):
        """ Returns the transaction id. """
        out, error, code = yield self._cli_cmnd('abandonclaim', txid, address, str(amount))
        defer.returnValue(out.strip())

    def decoderawtransaction(self, tx):
        return self._cli_cmnd('decoderawtransaction', tx)

    @defer.inlineCallbacks
    def getnameproof(self, name, *args):
        out, _, _ = yield self._cli_cmnd('getnameproof', name, *args)
        defer.returnValue(json.loads(out.strip()))

    @defer.inlineCallbacks
    def validateaddress(self, address):
        out, error, code = yield self._cli_cmnd('validateaddress', address)
        if error:
            defer.fail((out, code))
        else:
            defer.returnValue(json.loads(out))

    @defer.inlineCallbacks
    def getclaimsfortx(self, txid):
        out, error, code = yield self._cli_cmnd('getclaimsfortx', txid)
        if error:
            defer.fail((out, code))
        else:
            defer.returnValue(json.loads(out))

    @defer.inlineCallbacks
    def getrawtransaction(self, txid):
        out, error, code = yield self._cli_cmnd('getrawtransaction', txid, '1')
        if error:
            defer.fail((out, code))
        else:
            defer.returnValue(json.loads(out))

    @defer.inlineCallbacks
    def getclaimsforname(self, txid):
        out, error, code = yield self._cli_cmnd('getclaimsforname', txid)
        if error:
            defer.fail((out, code))
        else:
            defer.returnValue(json.loads(out))

    def claimname(self, name, value, amount):
        return self._cli_cmnd('claimname', name, value, str(amount))

    @defer.inlineCallbacks
    def supportclaim(self, name, claim_id, amount):
        out, error, code = yield self._cli_cmnd('supportclaim', name, claim_id, str(amount))
        if error:
            defer.fail((out, code))
        else:
            defer.returnValue(out.strip())
