import scipy.signal
import asyncio
import argparse
import numpy as np

import joule


ARGS_DESC = """
---
:name:
  Median Filter
:author:
  John Donnal
:license:
  Open
:url:
  http://git.wattsworth.net/wattsworth/joule.git
:usage:
    Apply a windowed median filter to the input stream.
    
    | Arguments | Description                     |
    |-----------|---------------------------------|
    |``window`` | samples to average, must be odd |


:inputs:
  input
  :  **<any type>** with N elements

:outputs:
  output
  :  **float32** with N elements

:stream_configs:
  #input#
     [Main]
     name = Raw Data
     path = /path/to/input
     datatype = int32
     keep = 1w

     [Element1]
     name = Element 1

     [Element2]
     name = Element 2

     #additional elements...

  #output#
     [Main]
     name = Filtered Data
     path = /path/to/output
     datatype = float32
     keep = 1w

     #same number of elements as input
     [Element1]
     name = Element 1

     [Element2]
     name = Element 2

     #additional elements...

:module_config:
    [Main]
    name = Mean Filter
    exec_cmd = joule-median-filter

    [Arguments]
    window = 11 # must be odd

    [Inputs]
    input = /path/to/input

    [Outputs]
    output = /path/to/output
---
"""


class MedianFilter(joule.FilterModule):
    "Compute the median of the input"

    def __init__(self):
        super(MedianFilter, self).__init__()

    def custom_args(self, parser):
        parser.add_argument("window", type=int,
                            help="window length")
        parser.description = ARGS_DESC
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

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


def main():
    r = MedianFilter()
    r.start()

    
if __name__ == "__main__":
    main()
