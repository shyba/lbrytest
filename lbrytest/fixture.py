import os
import shutil
import zipfile
from random import Random

from twisted.internet import defer, reactor

from lbrynet.core.utils import generate_id
from lbryschema.claim import ClaimDict
from lbrytest.wrapper import Lbrycrd


class Fixture:

    def __init__(self, lbrycrd, blocks=100, seed=2015):
        self.lbrycrd = lbrycrd
        self.blocks = blocks
        self.random = Random(seed)

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
        for block in range(self.blocks):
            for _ in range(self.random.randrange(10)):
                txn = self.random.randint(1, 100)
                name = 'name{}'.format(txn)
                claim = self._claim()
                amount = self.random.randrange(1, 5)/1000.0
                yield self.lbrycrd.claimname(
                    name, claim.serialized.encode('hex'), amount
                )
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
    lbrycrd = Lbrycrd(verbose=True)
    lbrycrd.setup()
    fixture = Fixture(lbrycrd)
    yield lbrycrd.start()
    yield lbrycrd.generate(110)
    yield fixture.load()
    yield lbrycrd.stop(cleanup=False)
    fixture.save()
    lbrycrd.cleanup()


if __name__ == "__main__":
    generate_test_chain()
    reactor.run()
