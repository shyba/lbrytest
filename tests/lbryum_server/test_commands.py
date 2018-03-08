import json

from lbrytest.case import IntegrationTestCase
from twisted.internet import defer


class CommandsTestCase(IntegrationTestCase):

    @defer.inlineCallbacks
    def test_tx_confirmation_related_commands(self):
        address = yield self.wallet.get_least_used_address()
        empty_history = self.lbry.stratum_command('blockchain.address.get_history', address)
        self.assertEqual(empty_history, [])

        sendtxid = yield self.lbrycrd.sendtoaddress(address, 2.5)

        mempool = self.lbry.stratum_command('blockchain.address.get_mempool', address)
        self.assertEqual(mempool, [{'tx_hash': sendtxid, 'height': 0}])
        unconfirmed_history = self.lbry.stratum_command('blockchain.address.get_history', address)
        self.assertEqual(unconfirmed_history, [{'tx_hash': sendtxid, 'height': 0}])
        unconfirmed_balance = self.lbry.stratum_command('blockchain.address.get_balance', address)
        self.assertEqual(unconfirmed_balance, {'confirmed': 0, 'unconfirmed': 250000000})

        yield self.lbrycrd.generate(1)
        yield self.lbry.wallet.wait_for_tx_in_wallet(sendtxid)

        updated_history = self.lbry.stratum_command('blockchain.address.get_history', address)
        self.assertEqual(updated_history, [{'tx_hash': sendtxid, 'height': 111}])
        empty_mempool = self.lbry.stratum_command('blockchain.address.get_mempool', address)
        self.assertEqual(empty_mempool, [])
        addresses = []
        for output in [0, 1]:
            addresses.append(self.lbry.stratum_command('blockchain.utxo.get_address', sendtxid, output))
        self.assertIn(address, addresses)
        txpos = addresses.index(address)
        self.assertEqual(empty_mempool, [])
        confirmed_unspent = self.lbry.stratum_command('blockchain.address.listunspent', address)
        self.assertEqual(confirmed_unspent, [{'height': 111, 'tx_hash': sendtxid, 'value': 250000000, 'tx_pos': txpos}])
        confirmed_balance = self.lbry.stratum_command('blockchain.address.get_balance', address)
        self.assertEqual(confirmed_balance, {'unconfirmed': 0, 'confirmed': 250000000})

    @defer.inlineCallbacks
    def test_supported_claim_confirmation(self):
        self.maxDiff = None
        # claim on unconfirmed tx
        claimtxid = (yield self.lbrycrd.claimname('@me', 'bebacafe', 0.1))[0].strip()
        raw_claimtx = yield self.lbrycrd.getrawtransaction(claimtxid)

        nameproof = yield self.lbrycrd.getnameproof('@me')
        claimtrie = yield self.lbry.stratum_command('blockchain.claimtrie.getvalue', '@me')
        self.assertEqual(claimtrie['proof'], nameproof)
        self.assertEqual(claimtrie['supports'], [])

        claims = yield self.lbry.stratum_command('blockchain.claimtrie.getclaimsintx', claimtxid)
        self.assertEqual(claims, [{}])  # weird
        # claim on confirmed tx
        block_hash = (yield self.lbrycrd.generate(10))
        claim_info = yield self.lbrycrd.getclaimsforname('@me')
        claim_info = self._parse_claim_info(claim_info, '@me', 'bebacafe', depth=9)

        claimbyid = yield self.lbry.stratum_command('blockchain.claimtrie.getclaimbyid', claim_info['claim_id'])
        claim_address = claimbyid['address']
        validated_address = yield self.lbrycrd.validateaddress(claim_address)
        self.assertTrue(validated_address['ismine'])
        del claimbyid['address']
        self.assertEqual(claimbyid, claim_info)

        nameproof = yield self.lbrycrd.getnameproof('@me', block_hash[0])
        claimtrie = yield self.lbry.stratum_command('blockchain.claimtrie.getvalue', '@me', block_hash[0])
        self.assertEqual(claimtrie['transaction'], raw_claimtx['hex'])
        self.assertEqual(claimtrie['proof'], nameproof)
        self.assertEqual(claimtrie['supports'], [])
        # confirmed claim with unconfirmed support
        supporttxid = yield self.lbrycrd.supportclaim('@me', claim_info['claim_id'], 1.0)

        nameproof = yield self.lbrycrd.getnameproof('@me')
        claimtrie = yield self.lbry.stratum_command('blockchain.claimtrie.getvalue', '@me')
        self.assertEqual(claimtrie['proof'], nameproof)
        self.assertEqual(claimtrie['supports'], [])

        claimbyid = yield self.lbry.stratum_command('blockchain.claimtrie.getclaimbyid', claim_info['claim_id'])
        claim_address = claimbyid['address']
        validated_address = yield self.lbrycrd.validateaddress(claim_address)
        self.assertTrue(validated_address['ismine'])
        del claimbyid['address']
        self.assertEqual(claimbyid, claim_info)

        # confirmed claim + confirmed support
        yield self.lbrycrd.generate(10)
        claim_info = yield self.lbrycrd.getclaimsforname('@me')
        claim_info = self._parse_claim_info(claim_info, '@me', 'bebacafe', depth=19)

        nameproof = yield self.lbrycrd.getnameproof('@me')
        claimtrie = yield self.lbry.stratum_command('blockchain.claimtrie.getvalue', '@me')
        self.assertEqual(claimtrie['proof'], nameproof)
        self.assertEqual(claimtrie['supports'], claim_info['supports'])

        claimbyid = yield self.lbry.stratum_command('blockchain.claimtrie.getclaimbyid', claim_info['claim_id'])
        claim_address = claimbyid['address']
        validated_address = yield self.lbrycrd.validateaddress(claim_address)
        self.assertTrue(validated_address['ismine'])
        del claimbyid['address']
        self.assertEqual(claimbyid, claim_info)

    def _parse_claim_info(self, claim_info, name, value, sequence=1, depth=0):
        """
        Formats daemon claim data into a claim info as specified in the lbryum stratum API
        """
        claim = claim_info['claims'][0]
        parsed_supports = [[support['txid'], support['n'], support['nAmount']] for
                              support in claim['supports']]
        return {'claim_sequence': sequence, 'name': name, 'supports': parsed_supports,
                'valid_at_height': claim['nValidAtHeight'], 'amount': claim['nAmount'],
                'value': value.encode('hex'), 'height': claim['nHeight'], 'depth': depth, 'nout': claim['n'],
                'txid': claim['txid'], 'claim_id': claim['claimId'],
                'effective_amount': claim['nEffectiveAmount']}
