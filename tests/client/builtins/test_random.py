from joule import LocalPipe
import asyncio
import numpy as np
import argparse

from tests import helpers
from joule.client.builtins.random_reader import RandomReader

WIDTH = 2
RATE = 100


class TestRandomReader(helpers.AsyncTestCase):

    def test_generates_random_values(self):

        my_reader = RandomReader()
        loop = asyncio.new_event_loop()
        pipe = LocalPipe("float32_%d" % WIDTH, name="output")
        args = argparse.Namespace(width=WIDTH, rate=RATE, pipes="unset")

        loop.call_later(0.1, my_reader.stop)
        loop.run_until_complete(my_reader.run(args, pipe))
        loop.close()
        # check the results
        result = pipe.read_nowait()
        diffs = np.diff(result['timestamp'])
        self.assertEqual(np.mean(diffs), 1 / RATE * 1e6)
        self.assertEqual(np.shape(result['data'])[1], WIDTH)
