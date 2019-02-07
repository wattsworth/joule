import scipy.signal
import asyncio
import textwrap
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
    # must be odd
    window = 11

    [Inputs]
    input = /path/to/input

    [Outputs]
    output = /path/to/output
---
"""


class MedianFilter(joule.FilterModule):
    """Compute the median of the input"""

    def custom_args(self, parser):  # pragma: no cover
        grp = parser.add_argument_group("module",
                                        "module specific arguments")
        grp.add_argument("--window", type=int, required=True,
                         help="window length")
        parser.description = textwrap.dedent(ARGS_DESC)

    async def run(self, parsed_args, inputs, outputs):
        N = parsed_args.window
        stream_in = inputs["input"]
        stream_out = outputs["output"]
        while not self.stop_requested:
            sarray_in = await stream_in.read()
            # not enough data, wait for more
            if len(sarray_in) < (N * 2):
                # check if the pipe is closed
                if stream_in.closed:  # pragma: no cover
                    return
                # check if this is the end of an interval
                # if so we can't use this data so discard it
                if stream_in.end_of_interval:
                    stream_in.consume(len(sarray_in))
                    await stream_out.close_interval()
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
            # hard to isolate in test, usually hits line 109
            if stream_in.end_of_interval:  # pragma: no cover
                await stream_out.close_interval()
                # dump all of the data because we don't
                # want to mix median across intervals
                stream_in.consume(len(sarray_in))
            else:
                stream_in.consume(len(sarray_out))


def main():  # pragma: no cover
    r = MedianFilter()
    r.start()

    
if __name__ == "__main__":
    main()
