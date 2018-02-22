import time
from lbrytest.case import IntegrationTestCase
from twisted.internet import defer, threads

import logging
logging.getLogger('lbrynet').setLevel(logging.DEBUG)
logging.getLogger('lbryum').setLevel(logging.DEBUG)


class ResolveTest(IntegrationTestCase):

    VERBOSE = True

    timeout = 600

    @defer.inlineCallbacks
    def test_resolve(self):
        address = yield self.lbry.wallet.get_least_used_address()
        yield self.lbrycrd.sendtoaddress(address, 9.0)
        yield self.lbrycrd.generate(1)
        yield threads.deferToThread(time.sleep, 1)
        yield self.lbry.wallet.update_balance()
        self.assertEqual(self.lbry.wallet.get_balance(), 9.0)

        claims = []
        for claim_number in range(50):
            name = '@test{}'.format(claim_number)
            claim = yield self.lbry.wallet.claim_new_channel(name, 0.01)
            claims.append(claim)
            if claim_number % 23 == 0:
                yield self.lbrycrd.generate(1)
