from orchstr8.case import IntegrationTestCase
from twisted.internet import defer


class BalanceTest(IntegrationTestCase):

    @defer.inlineCallbacks
    def test_balance(self):
        yield self.wallet.update_balance()
        self.assertEqual(self.wallet.wallet_balance, 0)

        address = yield self.wallet.get_least_used_address()
        sendtxid = yield self.lbrycrd.sendtoaddress(address, 2.5)
        yield self.lbrycrd.generate(1)
        yield self.lbry.wallet.wait_for_tx_in_wallet(sendtxid)

        yield self.lbry.wallet.update_balance()
        self.assertEqual(self.lbry.wallet.wallet_balance, 2.5)
