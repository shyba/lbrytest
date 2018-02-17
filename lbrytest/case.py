from twisted.trial import unittest
from lbrycrd import Lbrycrd


class IntegrationTestCase(unittest.TestCase):

    #@classmethod
    #def setUpClass(cls):
    #    lbrycrd = Lbrycrd()
    #    lbrycrd.ensure()
    #    cls.lbrycrd = lbrycrd
    #    cls.setUpLbrycrd()

    @classmethod
    def setUpLbrycrd(cls):
        """ Setup blockchain to be used by tests. """

    #@classmethod
    #def tearDownClass(cls):
    #    cls.lbrycrd.teardown()
