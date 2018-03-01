from twisted.trial import unittest
from twisted.internet import defer
from lbrytest.wrapper import startup, shutdown
from lbrytest.fixture import Fixture


class IntegrationTestCase(unittest.TestCase):

    VERBOSE = False
    USE_FIXTURE = False

    def setUp(self):
        return startup(self, self.VERBOSE, self.setUpFixture, self.setUpLbrycrd)

    def setUpFixture(self):
        """ Called before lbrycrd is started to extract a fresh
            blockchain fixture. May return Deferred."""
        if self.USE_FIXTURE:
            fixture = Fixture()
            fixture.lbrycrd = self.lbrycrd
            fixture.extract()

    def setUpLbrycrd(self):
        """ Called after lbrycrd is started to do any further setup
            before starting lbryum-server. May return Deferred. """
        if not self.USE_FIXTURE:
            return self.lbrycrd.generate(110)

    def tearDown(self):
        return shutdown(self)
