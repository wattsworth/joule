import numpy as np
import asyncio

import joule


class FIRFilter(joule.FilterModule):
    "Apply Type I or IV FIR filter to the input"

    def __init__(self):
        super(FIRFilter, self).__init__()
        self.stop_requested = False

    def make_filter(self, parsed_args):
        # return [taps...]
        assert False  # implement in child
        
    async def run(self, parsed_args, inputs, outputs):
        stream_in = inputs["input"]
        stream_out = outputs["output"]
        taps = self.make_filter(parsed_args)
        N = len(taps)
        assert N % 2 != 0, "Tap count must be odd"
        print("Starting %d tap FIR filter " % N)
        while(not self.stop_requested):
            sarray_in = await stream_in.read()
            # not enough data, wait for more
            if(len(sarray_in) < (N * 2)):
                await asyncio.sleep(0.1)
                continue
            # allocate output array
            output_len = len(sarray_in)-N+1
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
        
    def stop(self):
        self.stop_requested = True
