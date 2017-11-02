from .filter import FilterModule
import numpy as np
import logging
import asyncio


"""
How this works:
Window Size: 5 (must be odd)
Input:           --------------------------------------
Output:          oo----------------------------------
Input Consumed:  ----------------------------------oooo

So the time stamps must be sliced to match the actual output:
   ts_out = ts_in[bound:-bound] where bound=floor(window/2)
"""


class MeanFilter(FilterModule):
    "Compute the moving average of the input"

    def __init__(self):
        super(MeanFilter, self).__init__("Mean Filter")
        self.stop_requested = False
        self.description = "compute moving average"
        self.help = """
This is a filter that computes the element-wise
moving average of the input stream.
Specify the windown length (must be odd)
Example:
    joule filter mean 5 #moving avg of last 5 samples
"""
    
    def custom_args(self, parser):
        parser.add_argument("window", type=int,
                            help="window length")
        
    def runtime_help(self, parsed_args):
        return "moving average filter with a window size of %d" % parsed_args.window

    async def run(self, parsed_args, inputs, outputs):
        stream_in = inputs["input"]
        stream_out = outputs["output"]
        N = parsed_args.window
        assert N % 2 != 0, "Window size must be odd"
        logging.info("Starting moving average filter with window size %d" % N)
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
                                           data_in, np.ones((N,))/N,
                                           mode='valid')
            sarray_out['data'] = data_out
            await stream_out.write(sarray_out)
            stream_in.consume(output_len)
        
    def stop(self):
        self.stop_requested = True
            
if __name__ == "__main__":
    r = MeanFilter()
    r.start()
