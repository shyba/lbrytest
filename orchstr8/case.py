from twisted.trial import unittest
from orchstr8.wrapper import LbryServiceStack
from orchstr8.fixture import Fixture


class IntegrationTestCase(unittest.TestCase):

    VERBOSE = False
    USE_FIXTURE = False

    def setUp(self):
        self.service = LbryServiceStack(self.VERBOSE)
        return self.service.startup(self.setUpFixture, self.setUpLbrycrd)

    def setUpFixture(self):
        """ Called before lbrycrd is started to extract a fresh
            blockchain fixture. May return Deferred."""
        if self.USE_FIXTURE:
            fixture = Fixture()
            fixture.lbrycrd = self.service.lbrycrd
            fixture.extract()

    def setUpLbrycrd(self):
        """ Called after lbrycrd is started to do any further setup
            before starting lbryum-server. May return Deferred. """
        if not self.USE_FIXTURE:
            return self.service.lbrycrd.generate(110)

    def tearDown(self):
        return self.service.shutdown()

    @property
    def lbry(self):
        return self.service.lbry

    @property
    def lbrycrd(self):
        return self.service.lbrycrd

    @property
    def wallet(self):
        return self.lbry.wallet
