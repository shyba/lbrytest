import os
import time
from random import Random

from pyqtgraph.Qt import QtCore, QtGui
app = QtGui.QApplication([])
from qtreactor import pyqt4reactor
pyqt4reactor.install()

from twisted.internet import defer, task
from orchstr8.wrapper import LbryServiceStack

import pyqtgraph as pg
import numpy as np


class ThePublisherOfThings:

    def __init__(self, blocks=100, txns_per_block=100, seed=2015, start_blocks=110):
        self.blocks = blocks
        self.txns_per_block = txns_per_block
        self.start_blocks = start_blocks
        self.random = Random(seed)
        self.service = LbryServiceStack(verbose=True)
        self.publish_file = None

    @defer.inlineCallbacks
    def start(self):
        yield self.service.startup(
            after_lbrycrd_start=lambda: self.service.lbrycrd.generate(1010)
        )
        wallet = self.service.lbry.wallet
        address = yield wallet.get_least_used_address()
        sendtxid = yield self.service.lbrycrd.sendtoaddress(address, 100)
        yield self.service.lbrycrd.generate(1)
        yield wallet.wait_for_tx_in_wallet(sendtxid)
        yield wallet.update_balance()
        self.publish_file = os.path.join(self.service.lbry.download_directory, 'the_file')
        with open(self.publish_file, 'w') as _publish_file:
            _publish_file.write('message that will be heard around the world\n')

    @defer.inlineCallbacks
    def generate_publishes(self):

        win = pg.GraphicsLayoutWidget(show=True)
        win.setWindowTitle('orchstr8: performance monitor')
        win.resize(1000, 600)
        #p1 = win.addPlot(title="Basic array plotting", y=np.random.normal(size=100))

        p4 = win.addPlot()
        p4.setDownsampling(mode='peak')
        p4.setClipToView(True)
        curve4 = p4.plot()
        times = []

        for block in range(self.blocks):
            for txn in range(self.txns_per_block):
                name = 'block{}txn{}'.format(block, txn)
                start = time.time()
                yield self.service.lbry.daemon.jsonrpc_publish(
                    name=name, bid=self.random.randrange(1, 5)/1000.0,
                    file_path=self.publish_file, metadata={
                        "description": "Some interesting content",
                        "title": "My interesting content",
                        "author": "Video shot by me@example.com",
                        "language": "en", "license": "LBRY Inc", "nsfw": False
                    }
                )
                times.append(time.time() - start)
                curve4.setData(times)

            yield self.service.lbrycrd.generate(1)

    def stop(self):
        return self.service.shutdown(cleanup=False)


@defer.inlineCallbacks
def generate_publishes(_):
    pub = ThePublisherOfThings(5, 10)
    yield pub.start()
    yield pub.generate_publishes()
    yield pub.stop()
    print('lbrycrd: {}'.format(pub.service.lbrycrd.data_path))
    print('lbrynet: {}'.format(pub.service.lbry.data_path))
    print('lbryumserver: {}'.format(pub.service.lbryumserver.data_path))


if __name__ == "__main__":
    task.react(generate_publishes)
