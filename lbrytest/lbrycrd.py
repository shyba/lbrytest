import os
import signal
import shutil
import zipfile
import tempfile

import requests
from twisted.internet import reactor, defer, utils
from twisted.internet.protocol import ProcessProtocol


class LbrycrdProcess(ProcessProtocol):

    def __init__(self):
        self.running = defer.Deferred()
        self.stopped = defer.Deferred()
        self.errored = False

    def outReceived(self, data):
        print(data)
        if 'Error:' in data:
            self.errored = True
            self.running.callback(False)
        if 'Done loading' in data:
            self.running.callback(True)

    def processEnded(self, reason):
        print('process ended')
        self.stopped.callback(reason)

    def processExited(self, reason):
        print('process exited')
        self.stopped.callback(reason)

    def stop(self):
        print('stop()')
        if self.transport.pid:
            print('kill()')
            os.kill(self.transport.pid, signal.SIGHUP)
            print('kill finished')
            return self.stopped
        print('already stopped')
        return defer.succeed(0)


class Lbrycrd:

    def __init__(self, parent_path=None, bin_path=None):
        self.parent_data_path = parent_path
        self.data_path = None
        self.project_dir = os.path.dirname(os.path.dirname(__file__))
        self.lbrycrd_dir = bin_path or os.path.join(self.project_dir, 'bin')
        self.lbrycrd_zip = 'lbrycrd-linux.zip'
        self.zip_path = os.path.join(self.lbrycrd_dir, self.lbrycrd_zip)
        self.lbrycrd_cli_path = os.path.join(self.lbrycrd_dir, 'lbrycrd-cli')
        self.lbrycrdd_path = os.path.join(self.lbrycrd_dir, 'lbrycrdd')

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
        return True

    def ensure(self):
        return self.exists or self.download()

    @defer.inlineCallbacks
    def start(self, with_blocks=101):
        self.ensure()
        self.data_path = tempfile.mkdtemp()
        if self.parent_data_path and os.path.exists(self.parent_data_path):
            shutil.copytree(self.parent_data_path, self.data_path)
        self.process = LbrycrdProcess()
        reactor.spawnProcess(
            self.process, self.lbrycrdd_path, [
                self.lbrycrdd_path,
                '-datadir={}'.format(self.data_path),
                '-printtoconsole', '-regtest', '-server',
            ]
        )
        yield self.process.running
        if with_blocks:
            yield utils.getProcessValue(
                self.lbrycrd_cli_path, [
                    '-datadir={}'.format(self.data_path),
                    '-regtest', 'generate', str(with_blocks),
                ]
            )
        print('started...')
        defer.returnValue(True)

    def stop(self):
        return self.process.stop()


if __name__ == "__main__":
    Lbrycrd().ensure()
