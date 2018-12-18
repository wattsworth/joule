
from ..reader_module import ReaderModule
from joule import utilities
import asyncio
import numpy as np
import textwrap

ARGS_DESC = """
---
:name:
  Random Reader
:author:
  John Donnal
:license:
  Open
:url:
  http://git.wattsworth.net/wattsworth/joule.git
:description:
  generate a random data stream
:usage:
    This is a module that generates random numbers.
    Specify width (number of elements) and the rate in Hz.
    
    | Arguments | Description        |
    |-----------|--------------------|
    |``width``      | number of elements |
    |``rate``       | data rate in Hz    |

:inputs:
  None

:outputs:
  output
  :  float32 with N elements specified by [width] argument

:stream_configs:
  #output#
     [Main]
     name = Random Data
     path = /path/to/output
     datatype = float32
     keep = 1w

     # [width] number of elements
     [Element1]
     name = Random Set 1

     [Element2]
     name = Random Set 2

     #additional elements...

:module_config:
    [Main]
    name = Random Reader
    exec_cmd = joule modules random-reader

    [Arguments]
    # number of elements
    width = 4
    # data rate in Hz
    rate = 10 

    [Outputs]
    output = /path/to/output
---
"""

OUTPUT_RATE = 1  # run in 1 second blocks


class RandomReader(ReaderModule):
    """Generate a random stream of data"""

    def custom_args(self, parser):  # pragma: no cover
        grp = parser.add_argument_group("module",
                                        "module specific arguments")
        grp.add_argument("--width", type=int,
                         required=True,
                         help="number of elements in output")
        grp.add_argument("--rate", type=float,
                         required=True,
                         help="rate in Hz")
        parser.description = textwrap.dedent(ARGS_DESC)

    async def run(self, parsed_args, output):
        # produce output four times per second
        # figure out how much output will be in each block
        rate = parsed_args.rate
        width = parsed_args.width
        data_ts = utilities.time_now()
        data_ts_inc = 1/rate*1e6
        wait_time = 1/OUTPUT_RATE
        BLOCK_SIZE = rate/OUTPUT_RATE
        fraction_remaining = 0
        i = 0
        # print("Starting random stream: %d elements @ %0.1fHz" % (width, rate))
        while not self.stop_requested:
            float_block_size = BLOCK_SIZE+fraction_remaining
            int_block_size = int(np.floor(float_block_size))
            fraction_remaining = float_block_size - int_block_size
            data = np.random.rand(int_block_size, width)
            self.avg = np.average(data)
            self.stddev = np.std(data)
            top_ts = data_ts + int_block_size*data_ts_inc
            ts = np.array(np.linspace(data_ts, top_ts,
                                      int_block_size, endpoint=False),
                          dtype=np.uint64)
            data_ts = top_ts
            await output.write(np.hstack((ts[:, None], data)))
            await asyncio.sleep(wait_time)
            i += 1


def main():  # pragma: no cover
    r = RandomReader()
    r.start()


if __name__ == "__main__":
    main()
