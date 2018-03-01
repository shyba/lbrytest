import os
import time
import shutil
import zipfile
from random import Random

from twisted.internet import defer, reactor, threads
defer.Deferred.debug = True

from lbrynet.core.utils import generate_id
from lbryschema.claim import ClaimDict
from lbrytest.wrapper import startup, shutdown

import logging
logging.getLogger('lbrynet').setLevel(logging.DEBUG)
logging.getLogger('lbryum').setLevel(logging.DEBUG)


class Fixture:

    def __init__(self, blocks=100, txns_per_block=100, seed=2015):
        self.blocks = blocks
        self.txns_per_block = txns_per_block
        self.random = Random(seed)
        # set by startup():
        self.lbrycrd = None
        self.lbry = None

    def start(self):
        return startup(self, verbose=True)

    def stop(self):
        return shutdown(self, cleanup=False)

    def cleanup(self):
        self.lbrycrd.cleanup()

    @property
    def data_dir(self):
        return os.path.join(self.lbrycrd.project_dir, 'data')

    @property
    def blockchain_base_filename(self):
        return os.path.join(self.data_dir, 'blockchain')

    @property
    def blockchain_zip_filename(self):
        return self.blockchain_base_filename + '.zip'

    @defer.inlineCallbacks
    def load(self):
        address = yield self.lbry.wallet.get_least_used_address()
        yield self.lbrycrd.sendtoaddress(address, 9.9)
        yield self.lbrycrd.generate(1)
        yield threads.deferToThread(time.sleep, 5)
        for block in range(self.blocks):
            for txn in range(self.txns_per_block):
                name = 'block{}txn{}'.format(block, txn)
                amount = self.random.randrange(1, 5)/1000.0
                claim = yield self.lbry.wallet.claim_new_channel('@'+name, amount)
                yield self.lbry.wallet.wait_for_tx_in_wallet(claim['txid'])
            yield self.lbrycrd.generate(1)

    def save(self):
        if not os.path.exists(self.data_dir):
            os.mkdir(self.data_dir)
        if os.path.exists(self.blockchain_zip_filename):
            os.remove(self.blockchain_zip_filename)
        shutil.make_archive(
            self.blockchain_base_filename, "zip", self.lbrycrd.data_path
        )

    def extract(self):
        with zipfile.ZipFile(self.blockchain_zip_filename) as zf:
            zf.extractall(self.lbrycrd.data_path)

    def _claim(self):
        return ClaimDict.load_dict({
          "version": "_0_0_1",
          "claimType": "streamType",
          "stream": {
            "source": {
              "source": generate_id(self.random.getrandbits(512)).encode('hex'),
              "version": "_0_0_1",
              "contentType": "video/mp4",
              "sourceType": "lbry_sd_hash"
            },
            "version": "_0_0_1",
            "metadata": {
              "license": "LBRY Inc",
              "description": "What is LBRY? An introduction with Alex Tabarrok",
              "language": "en",
              "title": "What is LBRY?",
              "author": "Samuel Bryan",
              "version": "_0_1_0",
              "nsfw": False,
              "licenseUrl": "",
              "preview": "",
              "thumbnail": "https://s3.amazonaws.com/files.lbry.io/logo.png"
            }
          }
        })


@defer.inlineCallbacks
def generate_test_chain():
    fixture = Fixture(10, 10)
    yield fixture.start()
    yield fixture.load()
    yield fixture.stop()
    fixture.save()
    yield fixture.cleanup()


if __name__ == "__main__":
    generate_test_chain()
    reactor.run()
