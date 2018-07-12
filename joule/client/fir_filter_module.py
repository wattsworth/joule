import numpy as np
import asyncio
from aiohttp import web

from . import filter_module


class FIRFilterModule(filter_module.FilterModule):
    "Apply Type I or IV FIR filter to the input"


    def routes(self):
        return [
            web.get('/', self.index)
        ]

    def index(self, request):
        return web.Response(text="The average is %0.2f and the stddev is %0.2f" %
                                 (self.avg, self.stddev))

    def make_filter(self, parsed_args):
        # return [taps...]
        assert False  # implement in child
        
    async def run(self, parsed_args, inputs, outputs):
        stream_in = inputs["input"]
        stream_out = outputs["output"]
        taps = self.make_filter(parsed_args)
        N = len(taps)
        assert N % 2 != 0, "Tap count must be odd"
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
            self.avg = np.average(data_out)
            self.stddev = np.std(data_out)
            sarray_out['data'] = data_out
            await stream_out.write(sarray_out)
            stream_in.consume(output_len)
        
