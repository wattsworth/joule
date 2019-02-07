#!/usr/bin/env python3

from joule.utilities import time_now
import joule
import asyncio
import numpy as np


class Counter(joule.ReaderModule):
    "Counts up from 0 at 10Hz"

    def custom_args(self, parser):
        parser.add_argument("--step", type=int, default=1,
                            help="apply an offset")
        
    async def run(self, parsed_args, output):

        count = 0
        while not self.stop_requested:
            await output.write(np.array([[time_now(), count]]))
            await asyncio.sleep(0.1)
            count += parsed_args.step

            
if __name__ == "__main__":
    r = Counter()
    r.start()
