import time

import shutil

import os

from lbrytest.case import IntegrationTestCase
from twisted.internet import defer, threads

import logging
log = logging.getLogger()
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(name)s:%(lineno)d: %(message)s"))
log.addHandler(handler)
log.setLevel(logging.DEBUG)
logging.getLogger('lbrynet').setLevel(logging.DEBUG)
logging.getLogger('lbryum').setLevel(logging.DEBUG)


class AbandonClaimLookup(IntegrationTestCase):

    VERBOSE = True

    def _backup_wallet(self, name):
        data_path = os.path.join(self.lbry.data_path, 'lbryum')
        default_wallet = os.path.join(data_path, 'wallets', 'default_wallet')
        backup_path = os.path.join(self.lbry.data_path, name)
        shutil.copyfile(default_wallet, backup_path)

    def _reset_lbryum_data(self):
        lbryum_dir = os.path.join(self.lbry.data_path, 'lbryum')
        shutil.rmtree(lbryum_dir)
        os.mkdir(lbryum_dir)
        os.mkdir(os.path.join(lbryum_dir, 'wallets'))

    @defer.inlineCallbacks
    def _restore_backup(self, name):
        yield self.lbry.stop()
        data_path = os.path.join(self.lbry.data_path, 'lbryum')
        default_wallet = os.path.join(data_path, 'wallets', 'default_wallet')
        backup_path = os.path.join(self.lbry.data_path, name)
        shutil.copyfile(backup_path, default_wallet)
        yield self.lbry.start()

    @defer.inlineCallbacks
    def test_simple_backup(self):
        address = yield self.lbry.wallet.get_least_used_address()
        yield self.lbrycrd.sendtoaddress(address, 5)
        yield self.lbrycrd.generate(1)
        yield self.lbry.wallet.update_balance()
        self._backup_wallet('original_wallet')
        self._reset_lbryum_data()
        yield self._restore_backup('original_wallet')
        yield self.lbry.wallet.update_balance()
        yield threads.deferToThread(time.sleep, 2)
        self.assertEqual(self.lbry.wallet.get_balance(), 5)

    @defer.inlineCallbacks
    def test_new_address_used_after_backup(self):
        address = yield self.lbry.wallet.get_least_used_address()
        yield self.lbrycrd.sendtoaddress(address, 5)
        yield self.lbrycrd.generate(1)
        yield self.lbry.wallet.update_balance()
        self._backup_wallet('original_wallet')

        new_address = yield self.lbry.wallet.get_new_address()
        yield self.lbrycrd.sendtoaddress(new_address, 5)
        yield self.lbrycrd.generate(1)
        yield self.lbry.wallet.update_balance()

        self._reset_lbryum_data()
        yield self._restore_backup('original_wallet')
        yield self.lbry.wallet.update_balance()
        yield threads.deferToThread(time.sleep, 2)
        self.assertEqual(self.lbry.wallet.get_balance(), 10)
