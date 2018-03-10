import json

import time
from lbryschema.claim import ClaimDict
from lbryschema.decode import smart_decode
from lbryschema.schema import SECP256k1
from lbryschema.signer import get_signer
from lbryschema.uri import parse_lbry_uri

from lbrytest.case import IntegrationTestCase
from twisted.internet import defer, threads

"""
Integration tests for lbryum-server using stratum protocol
TODO: reorganize tests after it becomes clear which fixtures to use and how to better group in scenarios
"""

test_metadata = {
    'license': 'NASA',
    'version': '_0_1_0',
    'description': 'test',
    'language': 'en',
    'author': 'test',
    'title': 'test',
    'nsfw': False,
    'thumbnail': 'test'
}

test_claim_dict = {
    'version': '_0_0_1',
    'claimType': 'streamType',
    'stream': {'metadata': test_metadata, 'version': '_0_0_1', 'source':
        {'source': '8655f713819344980a9a0d67b198344e2c462c90f813e86f'
                   '0c63789ab0868031f25c54d0bb31af6658e997e2041806eb',
         'sourceType': 'lbry_sd_hash', 'contentType': 'video/mp4', 'version': '_0_0_1'},
               }}


class CommandsTestCase(IntegrationTestCase):

    @defer.inlineCallbacks
    def test_tx_confirmation_related_commands(self):
        """
        Basic stratum commands (from electrum spec)
            blockchain.address.get_history
            blockchain.address.get_mempool
            blockchain.address.get_balance
            blockchain.address.listunspent
            blockchain.utxo.get_address
        """
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
        """
        Basic custom commands for LBRY's claimtrie
            blockchain.claimtrie.getvalue
            blockchain.claimtrie.getclaimsintx
            blockchain.claimtrie.getclaimbyid
        """
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
        yield self.lbrycrd.supportclaim('@me', claim_info['claim_id'], 1.0)

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

    @defer.inlineCallbacks
    def test_claim_order(self):
        self.maxDiff = None
        txs, block_hashes = [], []
        for _ in range(5):
            txs.append((yield self.lbrycrd.claimname('@order_matters', 'bebacafe', 0.1))[0].strip())
            block_hashes.extend((yield self.lbrycrd.generate(1)))
        while not self.lbry.wallet.network.get_server_height() == 115:
            yield threads.deferToThread(time.sleep, 0.1)  # TODO: workaround for waiting on server height notification
        claim = yield self.lbry.stratum_command('blockchain.claimtrie.getnthclaimforname', '@order_matters', 0)
        self.assertEqual(claim, {})  # 1 based, so 0 has no results
        for index in range(1, 6):
            returned_claim = yield self.lbry.stratum_command('blockchain.claimtrie.getnthclaimforname', '@order_matters', index)
            daemon_claim_info = yield self.lbrycrd.getclaimsforname('@order_matters')

            self.assertEqual(returned_claim['claim_sequence'], index)

            claim_address = returned_claim['address']
            validated_address = yield self.lbrycrd.validateaddress(claim_address)
            self.assertTrue(validated_address['ismine'])

            daemon_claim_info = self._parse_claim_info(daemon_claim_info, '@order_matters', 'bebacafe',
                                                       depth=(5 - index), claim_id=returned_claim['claim_id'])
            daemon_claim_info['address'] = claim_address
            daemon_claim_info['claim_sequence'] = index

            self.assertEqual(daemon_claim_info, returned_claim)
        yield self.lbrycrd.abandonclaim(txs[3], claim_address, 0.1)  # abandon fourth claim
        yield self.lbrycrd.generate(1)
        while not self.lbry.wallet.network.get_server_height() == 116:
            yield threads.deferToThread(time.sleep, 0.1)  # TODO: workaround for waiting on server height notification
        no_fifth_claim = yield self.lbry.stratum_command('blockchain.claimtrie.getnthclaimforname', '@order_matters', 5)
        self.assertEqual(no_fifth_claim, {})
        fourth_claim = yield self.lbry.stratum_command('blockchain.claimtrie.getnthclaimforname', '@order_matters', 4)
        self.assertEqual(fourth_claim['claim_sequence'], 4)
        self.assertEqual(fourth_claim['txid'], txs[4])

    @defer.inlineCallbacks
    def test_signed_claim_order(self):
        self.maxDiff = None
        private_key = get_signer(SECP256k1).generate().private_key.to_pem()
        certificate = ClaimDict.generate_certificate(private_key, curve=SECP256k1)
        value = certificate.serialized.encode('hex')
        yield self.lbrycrd.claimname('@ordermatters', value, 0.1)
        yield self.lbrycrd.generate(1)
        while self.lbry.wallet.network.get_server_height() < 111:
            yield threads.deferToThread(time.sleep, 0.1)  # TODO: workaround for waiting on server height notification

        cert_claim = (yield self.lbry.stratum_command('blockchain.claimtrie.getclaimsforname', '@ordermatters'))
        cert_claim = cert_claim['claims'][0]
        signed_claims = []
        for _ in range(5):
            decoded_claim = smart_decode(test_claim_dict)
            signed = decoded_claim.sign(private_key, cert_claim['address'], cert_claim['claim_id'], curve=SECP256k1)
            value = signed.serialized.encode('hex')
            txid = (yield self.lbrycrd.claimname('@ordermatters', value, 0.1))[0].strip()
            yield self.lbrycrd.generate(1)
            claimed_id = (yield self.lbrycrd.getclaimsfortx(txid))[0]['claimId']
            signed_claims.append(claimed_id)
        while self.lbry.wallet.network.get_server_height() < 115:
            yield threads.deferToThread(time.sleep, 0.1)  # TODO: workaround for waiting on server height notification

        claim = yield self.lbry.stratum_command('blockchain.claimtrie.getclaimssignedbynthtoname', '@ordermatters', 0)
        self.assertFalse(claim)  # 1 based, so 0 has no results

        stratum_args = ('blockchain.claimtrie.getclaimssignedby', '@ordermatters')
        returned_claims = yield self.lbry.stratum_command(*stratum_args)
        self.assertEqual(len(returned_claims), 5)
        sequence = [claim['claim_sequence'] for claim in returned_claims]
        self.assertEqual(sequence, range(2, 7))

        stratum_args = ('blockchain.claimtrie.getclaimssignedbyid', cert_claim['claim_id'])
        returned_claims = yield self.lbry.stratum_command(*stratum_args)
        self.assertEqual(len(returned_claims), 5)
        sequence = [claim['claim_sequence'] for claim in returned_claims]
        self.assertEqual(sequence, range(2, 7))

        stratum_args = ('blockchain.claimtrie.getclaimssignedbynthtoname', '@ordermatters', 1)
        returned_claims = yield self.lbry.stratum_command(*stratum_args)
        self.assertEqual(len(returned_claims), 5)
        sequence = [claim['claim_sequence'] for claim in returned_claims]
        self.assertEqual(sequence, range(2, 7))

    @defer.inlineCallbacks
    def test_uri_batch_resolve_from_simple_to_takeover(self):
        """
        Doesn't account for supports. Just signed simple claim and channel claims with subpaths, followed by takeover
        Target commands:
            blockchain.claimtrie.getvaluesforuris
            blockchain.claimtrie.getvalueforuri
        for easier testing (since commands call each other), we assume the following to be working:
            (tested on other test cases)
            blockchain.claimtrie.getvalue
        TODO: This can be improved by fixtures or formatting data from lbrycrd commands
        """
        self.maxDiff = None
        uris = ['@one', '@one/two', '@one/twothree', 'four']
        uris = ['lbry://%s'%(uri) for uri in uris]
        claim_values = {}
        @defer.inlineCallbacks
        def __claim(uri, amount=1):
            name = parse_lbry_uri(uri).name
            secp256k1_private_key = get_signer(SECP256k1).generate().private_key.to_pem()
            claim = ClaimDict.generate_certificate(secp256k1_private_key, curve=SECP256k1)
            claim_values.setdefault(name, []).append(claim.serialized.encode('hex'))
            defer.returnValue((yield self.lbrycrd.claimname(name, claim_values[name][-1], amount))[0].strip())
        yield defer.gatherResults([__claim(uri) for uri in uris])
        block_hashes = yield self.lbrycrd.generate(1)
        while not self.lbry.wallet.network.get_server_height() > 110:
            yield threads.deferToThread(time.sleep, 0.1)  # TODO: workaround for waiting on server height notification
        # confirmed
        uri_claims = yield self.lbry.stratum_command('blockchain.claimtrie.getvaluesforuris', block_hashes[0], *uris)
        # winning (as all uris were defined)
        claim_ids = []
        for uri in uris:
            parsed_uri = parse_lbry_uri(uri)
            name = parsed_uri.name
            claimvalue = yield self.lbry.stratum_command('blockchain.claimtrie.getvalue', name, block_hashes[0])
            current_uri_result = uri_claims[uri]
            claim_key = 'certificate' if parsed_uri.is_channel else 'claim'
            claim = current_uri_result[claim_key]
            self.assertEqual('winning', claim['resolution_type'])
            self.assertEqual(claim['result'], claimvalue)
            claim_ids.append(claim['result']['claim_id'])
        # uri with claim id
        uris_with_claim_ids = []
        for uri, claim_id in zip(uris, claim_ids):
            parsed_uri = parse_lbry_uri(uri)
            parsed_uri.claim_id = claim_id
            uris_with_claim_ids.append(parsed_uri.to_uri_string())
        args = [block_hashes] + uris_with_claim_ids
        uri_claims = yield self.lbry.stratum_command('blockchain.claimtrie.getvaluesforuris', *args)
        for uri in uris_with_claim_ids:
            parsed_uri = parse_lbry_uri(uri)
            name = parsed_uri.name
            claim_info = yield self.lbrycrd.getclaimsforname(name)
            claim_info = self._parse_claim_info(claim_info, name, claim_values[name][0], claim_id=parsed_uri.claim_id)
            current_uri_result = uri_claims[uri]
            claim_key = 'certificate' if parsed_uri.is_channel else 'claim'
            claim = current_uri_result[claim_key]
            self.assertEqual('claim_id', claim['resolution_type'])
            # manually check some varying fields over possible values
            self.assertIn(claim['result']['claim_sequence'], range(1,4))
            claim_info['claim_sequence'] = claim['result']['claim_sequence']

            claim_address = claim['result']['address']
            validated_address = yield self.lbrycrd.validateaddress(claim_address)
            self.assertTrue(validated_address['ismine'])
            del claim['result']['address']

            self.assertIn(claim['result']['value'].decode('hex'), claim_values[name])
            claim_info['value'] = claim['result']['value']

            self.assertEqual(claim['result'], claim_info)
        self.assertEqual(len(uri_claims.keys()), len(uris))
        print(json.dumps(uri_claims, indent=4, sort_keys=True))
        yield __claim(uris[0], 10) # takeover just for the channel claim
        block_hashes = yield self.lbrycrd.generate(10)
        uri_claims = yield self.lbry.stratum_command('blockchain.claimtrie.getvaluesforuris', block_hashes[-1], *uris)
        print(json.dumps(uri_claims, indent=4, sort_keys=True))

    def _parse_claim_info(self, claim_info, name, value, sequence=1, depth=0, claim_id=None):
        """
        Formats daemon claim data into a claim info as specified in the lbryum stratum API
        """
        if not claim_id:
            claim = claim_info['claims'][0]
        else:
            for claim in claim_info['claims']:
                if claim['claimId'] == claim_id: break
        parsed_supports = [[support['txid'], support['n'], support['nAmount']] for
                              support in claim['supports']]
        return {'claim_sequence': sequence, 'name': name, 'supports': parsed_supports,
                'valid_at_height': claim['nValidAtHeight'], 'amount': claim['nAmount'],
                'value': value.encode('hex'), 'height': claim['nHeight'], 'depth': depth, 'nout': claim['n'],
                'txid': claim['txid'], 'claim_id': claim['claimId'],
                'effective_amount': claim['nEffectiveAmount']}
