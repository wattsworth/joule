#!/usr/bin/env python3

import joule
import numpy as np


class MergeSum(joule.FilterModule):
    " Sums two streams "

    def custom_args(self, parser):
        pass
        
    async def run(self, parsed_args, inputs, outputs):
        in1 = inputs["input1"]
        in2 = inputs["input2"]
        stream_out = outputs["output"]
        await self.align_inputs(in1, in2)
        
        while(1):
            sarray1 = await in1.read(flatten=True)
            sarray2 = await in2.read(flatten=True)
            size = min(len(sarray1), len(sarray2))
            
            sarray1[:size, 1:] += sarray2[:size, 1:]
            await stream_out.write(sarray1[:size])
            in1.consume(size)
            in2.consume(size)

    async def align_inputs(self, in1, in2):
        while(1):
            # find the max starting time
            sarray1 = await in1.read()
            sarray2 = await in2.read()
            max_ts = max(sarray1['time'][0],
                         sarray2['time'][0])
            
            idx1 = np.argwhere(sarray1['time'] == max_ts)
            if(len(idx1) == 0):
                in1.consume(len(sarray1))
                continue

            idx2 = np.argwhere(sarray2['time'] == max_ts)
            if(len(idx2) == 0):
                in2.consume(len(sarray2))
                continue
            
            # found valid indices in both arrays
            idx1 = idx1[0, 0]
            idx2 = idx2[0, 0]
            
            in1.consume(idx1)
            in2.consume(idx2)
            return

        
if __name__ == "__main__":
    r = MergeSum()
    r.start()
