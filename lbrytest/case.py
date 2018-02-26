from twisted.trial import unittest
from twisted.internet import defer, reactor
from lbrytest.wrapper import Lbrycrd, LbryumServer, Lbry
from lbrytest.fixture import Fixture

from lbrynet.core.call_later_manager import CallLaterManager


class IntegrationTestCase(unittest.TestCase):

    VERBOSE = False
    USE_FIXTURE = False

    @defer.inlineCallbacks
    def setUp(self):
        CallLaterManager.setup(reactor.callLater)
        self.lbrycrd = Lbrycrd(verbose=self.VERBOSE)
        self.lbrycrd.setup()
        if self.USE_FIXTURE:
            Fixture(self.lbrycrd).extract()
        yield self.lbrycrd.start()
        if not self.USE_FIXTURE:
            yield self.lbrycrd.generate(110)
        self.lbryumserver = LbryumServer(self.lbrycrd, verbose=self.VERBOSE)
        self.lbryumserver.start()  # defers to thread
        self.lbry = Lbry()
        yield self.lbry.start()

    @defer.inlineCallbacks
    def tearDown(self):
        try:
            yield self.lbry.stop()
        except:
            pass

        try:
            CallLaterManager.stop()
        except:
            pass

        try:
            yield self.lbryumserver.stop()
        except:
            pass

        yield self.lbrycrd.stop()
