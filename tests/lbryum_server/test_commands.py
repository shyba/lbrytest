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
        self.assertEqual(unconfirmed_balance, {'confirmed': 0, 'unconfirmed': 250000000})

        yield self.lbrycrd.generate(1)
        yield self.lbry.wallet.wait_for_tx_in_wallet(sendtxid)

        updated_history = self.lbry.stratum_command('blockchain.address.get_history', address)
        self.assertEqual(updated_history, [{'tx_hash': sendtxid, 'height': 111}])
        empty_mempool = self.lbry.stratum_command('blockchain.address.get_mempool', address)
        self.assertEqual(empty_mempool, [])
        addresses = []
        for output in [0, 1]:
            addresses.append(self.lbry.stratum_command('blockchain.utxo.get_address', sendtxid, output))
        self.assertIn(address, addresses)
        txpos = addresses.index(address)
        self.assertEqual(empty_mempool, [])
        confirmed_unspent = self.lbry.stratum_command('blockchain.address.listunspent', address)
        self.assertEqual(confirmed_unspent, [{'height': 111, 'tx_hash': sendtxid, 'value': 250000000, 'tx_pos': txpos}])
        confirmed_balance = self.lbry.stratum_command('blockchain.address.get_balance', address)
        self.assertEqual(confirmed_balance, {u'unconfirmed': 0, u'confirmed': 250000000})
