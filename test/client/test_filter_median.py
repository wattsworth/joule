from joule.utils.numpypipe import LocalNumpyPipe
import asynctest
import asyncio
import numpy as np
import numpy.matlib
import argparse
from joule.client.filters.median import MedianFilter


class TestMedianFilter(asynctest.TestCase):

    def test_computes_median(self):
        # data is a repeating series of 0,1,2,..N
        # the median of this array should be N/2
        # timestamps is just an increasing index

        WINDOW = 3
        WIDTH = 5
        REPS_PER_BLOCK = 9
        NUM_BLOCKS = 3
        my_filter = MedianFilter()
        pipe_in = LocalNumpyPipe("input", layout="float32_%d" % WIDTH)
        pipe_out = LocalNumpyPipe("output", layout="float32_%d" % WIDTH)
        args = argparse.Namespace(window=WINDOW, pipes="unset")
        base = np.array([np.arange(x, WINDOW+x) for x in range(WIDTH)]).T

        async def writer():
            prev_ts = 0
            for block in range(NUM_BLOCKS):
                data = numpy.matlib.repmat(base, REPS_PER_BLOCK, 1)
                ts = np.arange(prev_ts, prev_ts + len(data))
                input_block = np.hstack((ts[:, None], data))
                pipe_in.write_nowait(input_block)
                await asyncio.sleep(0.1)
                prev_ts = ts[-1]+1
            await asyncio.sleep(0.2)
            my_filter.stop()

        # run reader in an event loop
        loop = asyncio.get_event_loop()
        tasks = [asyncio.ensure_future(writer()),
                 my_filter.run(args, {"input": pipe_in},
                               {"output": pipe_out})]
        loop.run_until_complete(asyncio.gather(*tasks))
        
        loop.close()
        # check the results
        result = pipe_out.read_nowait()
        # expect the output to be a constant (WINDOW-1)/2
        # expect the output to be a constant (WINDOW-1)/2
        base_output = np.ones((WINDOW * REPS_PER_BLOCK *
                              NUM_BLOCKS - (WINDOW-1), WIDTH))
        expected = base_output*range(int(WINDOW/2), int(WINDOW/2) + WIDTH)
        np.testing.assert_array_equal(expected,
                                      result['data'])


