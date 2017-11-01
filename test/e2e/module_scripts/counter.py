#!/usr/bin/python3

from joule.utils.time import now as time_now
from joule.client import ReaderModule
import asyncio
import numpy as np


class Counter(ReaderModule):
    "Counts up from 0 at 100Hz"

    def __init__(self):
        super(Counter, self).__init__("Counter")
    
    def custom_args(self, parser):
        pass
        
    async def run(self, parsed_args, output):
        count = 0
        while(1):
            await output.write(np.array([[time_now(), count]]))
            await asyncio.sleep(0.01)
            count += 1

            
if __name__ == "__main__":
    r = Counter()
    r.start()
