import numpy as np
import asyncio

from . import filter_module
from joule.models.pipes import EmptyPipe, Pipe
from joule.utilities import timestamp_to_human

class FIRFilterModule(filter_module.FilterModule):
    """Apply Type I or IV FIR filter to the input"""

    def make_filter(self, parsed_args) -> np.ndarray:
        # return [taps...]
        #  implement in child
        assert False, "implement in child class"  # pragma: no cover

    async def run(self, parsed_args, inputs, outputs):
        stream_in: Pipe = inputs["input"]
        stream_out: Pipe = outputs["output"]
        taps = self.make_filter(parsed_args)
        N = len(taps)
        assert N % 2 != 0, "Tap count must be odd"
        while not self.stop_requested:
            try:
                sarray_in = await stream_in.read()
            except EmptyPipe:
                return

            if len(sarray_in) < (N * 2):
                # check if the pipe is closed
                if stream_in.closed:
                    return
                await asyncio.sleep(0.1)
                continue
            # not enough data, wait for more
            # allocate output array
            output_len = len(sarray_in) - N + 1
            sarray_out = np.zeros(output_len, dtype=stream_out.dtype)
            # moving average using convolution
            bound = int(N / 2)
            sarray_out['timestamp'] = sarray_in['timestamp'][bound:-bound]
            data_in = sarray_in['data']
            # run filter by column
            data_out = np.apply_along_axis(np.convolve, 0,
                                           data_in, taps,
                                           mode='valid')
            sarray_out['data'] = data_out
            await stream_out.write(sarray_out)
            stream_in.consume(output_len)
            if stream_in.end_of_interval:
                await stream_out.close_interval()
