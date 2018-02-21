from twisted.trial import unittest
from twisted.internet import defer
from lbrytest.wrapper import Lbrycrd, LbryumServer


class LbrycrdTestCase(unittest.TestCase):

    VERBOSE = False

    @defer.inlineCallbacks
    def setUp(self):
        self.lbrycrd = Lbrycrd(verbose=self.VERBOSE)
        yield self.lbrycrd.start()
        yield self.lbrycrd.generate(100)

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.lbrycrd.stop()


class LbryumServerTestCase(LbrycrdTestCase):

    @defer.inlineCallbacks
    def setUp(self):
        yield super(LbryumServerTestCase, self).setUp()
        self.lbryumserver = LbryumServer(self.lbrycrd, verbose=self.VERBOSE)
        self.lbryumserver.start()

    @defer.inlineCallbacks
    def tearDown(self):
        try:
            self.lbryumserver.stop()
        finally:
            yield super(LbryumServerTestCase, self).tearDown()


class LbryumTestCase(LbrycrdTestCase):

    @defer.inlineCallbacks
    def setUp(self):
        yield super(LbryumTestCase, self).setUp()
        self.lbryumserver = LbryumServer(self.lbrycrd, verbose=self.VERBOSE)
        self.lbryumserver.start()

    @defer.inlineCallbacks
    def tearDown(self):
        try:
            self.lbryumserver.stop()
        finally:
            yield super(LbryumTestCase, self).tearDown()
