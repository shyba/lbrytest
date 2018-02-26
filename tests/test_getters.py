import time
from lbrytest.case import IntegrationTestCase
from twisted.internet import defer, threads

import logging
logging.getLogger('lbrynet').setLevel(logging.DEBUG)
logging.getLogger('lbryum').setLevel(logging.DEBUG)


class ResolveTest(IntegrationTestCase):

    VERBOSE = True
    USE_FIXTURE = True

    @defer.inlineCallbacks
    def test_resolve(self):
        yield self.lbry.wallet.resolve('lbry://name5')
