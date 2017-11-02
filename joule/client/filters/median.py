from .filter import FilterModule
import scipy.signal
import asyncio
import numpy as np

"""
How this works:
Window Size: 5 (must be odd)
Input:           --------------------------------------
Output:          oo----------------------------------
Input Consumed:  ----------------------------------oooo

So the time stamps must be sliced to match the actual output:
   ts_out = ts_in[bound:-bound] where bound=floor(window/2)
"""


class MedianFilter(FilterModule):
    "Compute the moving average of the input"

    def __init__(self):
        super(MedianFilter, self).__init__("Median Filter")
        self.stop_requested = False
        self.description = "compute median"
        self.help = """
This is a filter that computes the element-wise
median of the input stream
Specify the windown length (must be odd)
Example:
    joule filter median 5 # 5-wide median
"""

    def custom_args(self, parser):
        parser.add_argument("window", type=int,
                            help="window length")

    def runtime_help(self, parsed_args):
        return "median filter with a window size of %d" % parsed_args.window

    async def run(self, parsed_args, inputs, outputs):
        N = parsed_args.window
        stream_in = inputs["input"]
        stream_out = outputs["output"]
        while(not self.stop_requested):
            sarray_in = await stream_in.read()
            # not enough data, wait for more
            if(len(sarray_in) < (N * 2)):
                await asyncio.sleep(0.1)
                continue
            # allocate output array
            output_len = len(sarray_in)-N+1
            sarray_out = np.zeros(output_len, dtype=stream_out.dtype)
            filtered = scipy.signal.medfilt(sarray_in['data'], [N, 1])
            bound = int(N / 2)
            sarray_out['data'] = filtered[bound:-bound]
            sarray_out['timestamp'] = sarray_in['timestamp'][bound:-bound]
            await stream_out.write(sarray_out)
            stream_in.consume(len(sarray_out))

    def stop(self):

        self.stop_requested = True
                
if __name__ == "__main__":
    r = MedianFilter()
    r.start()
