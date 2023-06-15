from joule import LocalPipe
import unittest
import asyncio
import numpy as np
import argparse

from tests import helpers
from joule.client.builtins.mean_filter import MeanFilter

WINDOW = 9
WIDTH = 4
REPS_PER_BLOCK = 9
NUM_BLOCKS = 3


class TestMeanFilter(helpers.AsyncTestCase):

    def test_computes_moving_average(self):
        # data is a repeating series of 0,1,2,..N
        # the moving average of this array should be N/2
        # timestamps is just an increasing index

        my_filter = MeanFilter()
        pipe_in = LocalPipe("float32_%d" % WIDTH, name="input")
        pipe_out = LocalPipe("float32_%d" % WIDTH, name="output")
        args = argparse.Namespace(window=WINDOW, pipes="unset")
        base = np.array([np.arange(x, WINDOW + x) for x in range(WIDTH)]).T

        async def writer():
            prev_ts = 0
            for block in range(NUM_BLOCKS):
                data = np.tile(base, (REPS_PER_BLOCK, 1))
                ts = np.arange(prev_ts, prev_ts + len(data))
                input_block = np.hstack((ts[:, None], data))
                pipe_in.write_nowait(input_block)
                # await asyncio.sleep(0.1)
                prev_ts = ts[-1] + 1
            # now put in an extra block after an interval break
            await pipe_in.close_interval()
            # all 1's (even timestamps)
            await pipe_in.write(np.ones((100, WIDTH + 1)))
            # await asyncio.sleep(0.2)
            await pipe_in.close()

        # run reader in an event loop
        async def runner():
            await asyncio.gather(writer(),
                           my_filter.run(args,
                                         {"input": pipe_in},
                                         {"output": pipe_out}))
        asyncio.run(runner())
        # check the results
        result = pipe_out.read_nowait()
        # expect the output to be a constant (WINDOW-1)/2
        base_output = np.ones((WINDOW * REPS_PER_BLOCK *
                               NUM_BLOCKS - (WINDOW - 1), WIDTH))
        expected = base_output * range(int(WINDOW / 2), int(WINDOW / 2) + WIDTH)
        np.testing.assert_array_equal(expected,
                                      result['data'])
        self.assertTrue(pipe_out.end_of_interval)
        pipe_out.consume(len(result))
        # now read the extra block and make sure it has all the data
        result = pipe_out.read_nowait(flatten=True)
        self.assertEqual(len(result), 100 - WINDOW + 1)
