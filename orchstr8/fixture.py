import os
import shutil
import zipfile
from random import Random

from twisted.internet import defer, task

from lbrynet.core.utils import generate_id
from lbryschema.claim import ClaimDict
from orchstr8.wrapper import Lbrycrd


class Fixture:

    def __init__(self, blocks=100, txns_per_block=100, seed=2015, start_blocks=110):
        self.blocks = blocks
        self.txns_per_block = txns_per_block
        self.start_blocks = start_blocks
        self.random = Random(seed)
        self.lbrycrd = Lbrycrd(verbose=True)

    @defer.inlineCallbacks
    def start(self):
        self.lbrycrd.setup()
        yield self.lbrycrd.start()
        yield self.lbrycrd.generate(self.start_blocks)

    @defer.inlineCallbacks
    def generate_transactions(self):
        for block in range(self.blocks):
            for txn in range(self.txns_per_block):
                name = 'block{}txn{}'.format(block, txn)
                amount = self.random.randrange(1, 5)/1000.0
                yield self.lbrycrd.claimname('@'+name, self._claim().serialized.encode('hex'), amount)
            yield self.lbrycrd.generate(1)

    def stop(self):
        return self.lbrycrd.stop(cleanup=False)

    def save(self):
        if not os.path.exists(self.data_dir):
            os.mkdir(self.data_dir)
        if os.path.exists(self.blockchain_zip_filename):
            os.remove(self.blockchain_zip_filename)
        shutil.make_archive(
            self.blockchain_base_filename, "zip", self.lbrycrd.data_path
        )

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
def generate_test_chain(_):
    fixture = Fixture(10, 10)
    yield fixture.start()
    yield fixture.generate_transactions()
    yield fixture.stop()
    fixture.save()
    fixture.cleanup()


if __name__ == "__main__":
    task.react(generate_test_chain)
