#!/usr/bin/env python3
"""
InStream1 ==> x2 ==> InStream2
InStream2 ==> x3 ==> OutStream2
"""


import joule
import argparse
import json

import adder

"""
run 1 or more adders
arguments:
  npaths = number of adders to run
  offsets = json array of offsets (len==npaths)

path1 --> + offset[0] --> path1
path2 --> + offset[1] --> path2
...more

"""


class CompositeAdder(joule.CompositeModule):
    " add offsets to input streams"

    def custom_args(self, parser):
        parser.add_argument("--npaths", type=int, required=True)
        parser.add_argument("--offsets",
                            required=True,
                            help="JSON array, length must equal npaths")
        
    async def setup(self, parsed_args, inputs, outputs):
        npaths = parsed_args.npaths
        offsets = json.loads(parsed_args.offsets)
        tasks = []
        for x in range(npaths):
            a = adder.Adder()
            args = argparse.Namespace(offset=offsets[x])
            t = a.run(args,
                      {"input": inputs["path%d" % (x+1)]},
                      {"output": outputs["path%d" % (x+1)]})
            tasks.append(t)
        return tasks

    
if __name__ == "__main__":
    r = CompositeAdder()
    r.start()
