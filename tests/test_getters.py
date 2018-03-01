from lbrytest.case import IntegrationTestCase
from twisted.internet import defer

import logging
logging.getLogger('lbrynet').setLevel(logging.DEBUG)
logging.getLogger('lbryum').setLevel(logging.DEBUG)


class BalanceTest(IntegrationTestCase):

    VERBOSE = True
    USE_FIXTURE = True

    @defer.inlineCallbacks
    def test_balance(self):
        address = yield self.lbry.wallet.get_least_used_address()
        sendtxid = yield self.lbrycrd.sendtoaddress(address, 1)
        yield self.lbrycrd.generate(1)
        yield self.lbry.wallet.wait_for_tx_in_wallet(sendtxid)
        print(self.lbry.wallet.wallet_balance)
        yield self.lbry.wallet.update_balance()
        print(self.lbry.wallet.wallet_balance)
        self.assertEqual(self.lbry.wallet.wallet_balance, 1)
