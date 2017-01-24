from joule.utils.time import now as time_now

from joule.client import ReaderModule
import asyncio
import numpy as np
import logging


class RandomReader(ReaderModule):
    "Generate a random stream of data"

    def __init__(self, output_rate=4):
        super(RandomReader, self).__init__("Random Reader")
        self.stop_requested = False
        self.output_rate = output_rate  # Hz, how often to push data
        self.description = "generate a random stream of data"
        self.help = """
This is a module that generates random numbers.
Specify width and the rate:
Example:
    $> joule reader random 3 1
        1485274511453066 0.29717862865048317
        1485274511553066 0.88548911551368858
        1485274511653066 0.099506076011947053
        1485274511753066 0.23619839742598503
        1485274511853066 0.97747567249867184
        # ....more output...
"""
    
    def custom_args(self, parser):
        parser.add_argument("width", type=int,
                            help="number of elements in output")
        parser.add_argument("rate", type=float,
                            help="rate in Hz")

    async def run(self, parsed_args, output):
        # produce output four times per second
        # figure out how much output will be in each block
        rate = parsed_args.rate
        width = parsed_args.width
        data_ts = time_now()
        data_ts_inc = 1/rate*1e6
        wait_time = 1/self.output_rate
        BLOCK_SIZE = rate/self.output_rate
        fraction_remaining = 0
        i = 0
        logging.info("Starting random stream: %d elements @ %0.1fHz" % (width, rate))
        while(not self.stop_requested):
            float_block_size = BLOCK_SIZE+fraction_remaining
            int_block_size = int(np.floor(float_block_size))
            fraction_remaining = float_block_size - int_block_size
            data = np.random.rand(int_block_size, width)
            top_ts = data_ts + int_block_size*data_ts_inc
            ts = np.array(np.linspace(data_ts, top_ts,
                                      int_block_size, endpoint=False),
                          dtype=np.uint64)
            data_ts = top_ts
            await output.write(np.hstack((ts[:, None], data)))
            await asyncio.sleep(wait_time)
            i += 1

    def stop(self):
        self.stop_requested = True

if __name__ == "__main__":
    r = RandomReader()
    r.start()
    
