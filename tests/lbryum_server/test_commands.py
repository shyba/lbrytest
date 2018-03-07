from lbrytest.case import IntegrationTestCase
from twisted.internet import defer


class CommandsTestCase(IntegrationTestCase):

    @defer.inlineCallbacks
    def test_tx_confirmation_related_commands(self):
        address = yield self.wallet.get_least_used_address()
        empty_history = self.lbry.stratum_command('blockchain.address.get_history', address)
        self.assertEqual(empty_history, [])

        sendtxid = yield self.lbrycrd.sendtoaddress(address, 2.5)

        mempool = self.lbry.stratum_command('blockchain.address.get_mempool', address)
        self.assertEqual(mempool, [{'tx_hash': sendtxid, 'height': 0}])
        unconfirmed_history = self.lbry.stratum_command('blockchain.address.get_history', address)
        self.assertEqual(unconfirmed_history, [{'tx_hash': sendtxid, 'height': 0}])
        unconfirmed_balance = self.lbry.stratum_command('blockchain.address.get_balance', address)
        self.assertEqual(unconfirmed_balance, {u'confirmed': 0, u'unconfirmed': 250000000})

        yield self.lbrycrd.generate(1)
        yield self.lbry.wallet.wait_for_tx_in_wallet(sendtxid)

        updated_history = self.lbry.stratum_command('blockchain.address.get_history', address)
        self.assertEqual(updated_history, [{'tx_hash': sendtxid, 'height': 111}])
        empty_mempool = self.lbry.stratum_command('blockchain.address.get_mempool', address)
        self.assertEqual(empty_mempool, [])
        confirmed_balance = self.lbry.stratum_command('blockchain.address.get_balance', address)
        self.assertEqual(confirmed_balance, {u'unconfirmed': 0, u'confirmed': 250000000})
