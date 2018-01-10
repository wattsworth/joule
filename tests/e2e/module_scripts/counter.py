#!/usr/bin/python3

from joule.utils.time import now as time_now
import joule
import asyncio
import numpy as np


class Counter(joule.ReaderModule):
    "Counts up from 0 at 100Hz"

    def custom_args(self, parser):
        parser.add_argument("--step", type=int, default=1,
                            help="apply an offset")
        
    async def run(self, parsed_args, output):

        count = 0
        while(not self.stop_requested):
            await output.write(np.array([[time_now(), count]]))
            await asyncio.sleep(0.01)
            count += parsed_args.step

            
if __name__ == "__main__":
    r = Counter()
    r.start()
