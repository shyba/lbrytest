import time

import shutil

import os

from lbrytest.case import IntegrationTestCase
from twisted.internet import defer, threads


class WalletBackupTestCase(IntegrationTestCase):

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
        yield threads.deferToThread(time.sleep, 5)
        self.assertEqual(self.lbry.wallet.get_balance(), 10)

    @defer.inlineCallbacks
    def test_big_wallet_after_backup(self):
        # From https://github.com/lbryio/lbryum/issues/155
        # It was reported loss of addresses after 10/20 new ones
        address = yield self.lbry.wallet.get_least_used_address()
        yield self.lbrycrd.sendtoaddress(address, 5)
        yield self.lbrycrd.generate(1)
        yield self.lbry.wallet.update_balance()
        self._backup_wallet('original_wallet')

        for _ in xrange(20):
            new_address = yield self.lbry.wallet.get_new_address()
        yield self.lbrycrd.sendtoaddress(new_address, 5)
        yield self.lbrycrd.generate(1)
        yield self.lbry.wallet.update_balance()
        yield threads.deferToThread(time.sleep, 10)
        self.assertEqual(self.lbry.wallet.get_balance(), 10)

        self._reset_lbryum_data()
        yield self._restore_backup('original_wallet')
        yield self.lbry.wallet.update_balance()
        yield threads.deferToThread(time.sleep, 10)
        yield self.lbry.wallet.update_balance()
        self.assertEqual(self.lbry.wallet.get_balance(), 10)

    @defer.inlineCallbacks
    def test_simple_claim_backup(self):
        address = yield self.lbry.wallet.get_least_used_address()
        yield self.lbrycrd.sendtoaddress(address, 1)
        yield self.lbrycrd.generate(1)
        yield self.lbry.networkDeferred
        yield self.lbry.wallet.update_balance()
        yield self.lbry.wallet.claim_new_channel('@beforeBackup', 0.5)
        yield self.lbrycrd.generate(1)
        self._backup_wallet('original_wallet')
        self._reset_lbryum_data()
        yield self._restore_backup('original_wallet')
        yield self.lbrycrd.sendtoaddress(address, 1)
        yield self.lbrycrd.generate(1)
        yield self.lbry.networkDeferred
        yield self.lbry.wallet.update_balance()
        channel_list = yield self.lbry.wallet.channel_list()
        self.assertEqual(len(channel_list), 1)
        self.assertEqual(channel_list[0]['name'], '@beforeBackup')

    @defer.inlineCallbacks
    def test_claim_after_backup(self):
        address = yield self.lbry.wallet.get_least_used_address()
        yield self.lbrycrd.sendtoaddress(address, 5)
        yield self.lbrycrd.generate(1)
        yield threads.deferToThread(time.sleep, 2)
        self._backup_wallet('original_wallet')
        yield self.lbry.wallet.update_balance()
        yield self.lbry.wallet.claim_new_channel('@beforeBackup', 1)
        yield self.lbrycrd.generate(1)
        yield threads.deferToThread(time.sleep, 2)
        self._reset_lbryum_data()
        yield self._restore_backup('original_wallet')
        yield self.lbry.wallet.update_balance()
        yield threads.deferToThread(time.sleep, 2)
        channel_list = yield self.lbry.wallet.channel_list()
        self.assertEqual(len(channel_list), 1)
        self.assertEqual(channel_list[0]['name'], '@beforeBackup')
