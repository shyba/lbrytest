from twisted.trial import unittest
from twisted.internet import defer
from lbrytest.wrapper import Lbrycrd, LbryumServer, Lbry


class IntegrationTestCase(unittest.TestCase):

    VERBOSE = False

    @defer.inlineCallbacks
    def setUp(self):
        self.lbrycrd = Lbrycrd(verbose=self.VERBOSE)
        yield self.lbrycrd.start()
        yield self.lbrycrd.generate(110)
        self.lbryumserver = LbryumServer(self.lbrycrd, verbose=self.VERBOSE)
        self.lbryumserver.start()  # defers to thread
        self.lbry = Lbry()
        yield self.lbry.start()
        address = yield self.lbry.wallet.get_least_used_address()
        yield self.lbrycrd.sendtoaddress(address, 50)
        yield self.lbrycrd.generate(6)
        yield self.lbry.wallet.update_balance()
        print(self.lbry.wallet.get_balance())

    @defer.inlineCallbacks
    def tearDown(self):
        try:
            yield self.lbry.stop()
        except:
            pass

        try:
            yield self.lbryumserver.stop()
        except:
            pass

        yield self.lbrycrd.stop()
