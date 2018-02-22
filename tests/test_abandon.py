import time
from lbrytest.case import IntegrationTestCase
from twisted.internet import defer, threads

import logging
log = logging.getLogger()
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(name)s:%(lineno)d: %(message)s"))
log.addHandler(handler)
log.setLevel(logging.DEBUG)
logging.getLogger('lbrynet').setLevel(logging.DEBUG)
logging.getLogger('lbryum').setLevel(logging.DEBUG)


class AbandonClaimLookup(IntegrationTestCase):

    VERBOSE = True

    @defer.inlineCallbacks
    def test_abandon_claim(self):
        address = yield self.lbry.wallet.get_least_used_address()
        yield self.lbrycrd.sendtoaddress(address, 0.0003 - 0.0000355)
        yield self.lbrycrd.generate(1)
        yield self.lbry.wallet.update_balance()
        yield threads.deferToThread(time.sleep, 5)
        print(self.lbry.wallet.get_balance())
        claim = yield self.lbry.wallet.claim_new_channel('@test', 0.000096)
        yield self.lbrycrd.generate(1)
        print('='*10 + 'CLAIM' + '='*10)
        print(claim)
        yield self.lbrycrd.decoderawtransaction(claim['tx'])
        abandon = yield self.lbry.wallet.abandon_claim(claim['claim_id'], claim['txid'], claim['nout'])
        print('='*10 + 'ABANDON' + '='*10)
        print(abandon)
        yield self.lbrycrd.decoderawtransaction(abandon['tx'])
        yield self.lbrycrd.generate(1)
        yield self.lbrycrd.getrawtransaction(abandon['txid'])

        yield self.lbry.wallet.update_balance()
        yield threads.deferToThread(time.sleep, 5)
        print('='*10 + 'FINAL BALANCE' + '='*10)
        print(self.lbry.wallet.get_balance())
