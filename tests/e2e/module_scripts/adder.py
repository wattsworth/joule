#!/usr/bin/env python3

import joule
import asyncio


class Adder(joule.FilterModule):
    """ Add DC offset to input """
    
    def custom_args(self, parser):
        parser.add_argument("offset", type=int, default=0,
                            help="apply an offset")
        
    async def run(self, parsed_args, inputs, outputs):
        stream_in: joule = inputs["input"]
        stream_out = outputs["output"]
        while not self.stop_requested:
            try:
                sarray = await stream_in.read()
                sarray["data"] += parsed_args.offset
                await asyncio.sleep(0.25)
                await stream_out.write(sarray)
                stream_in.consume(len(sarray))
                if stream_in.end_of_interval:
                    print("closing interval")
                    await stream_out.close_interval()

            except joule.EmptyPipe:
                print("got an empty pipe, exiting")
                exit(1)
            

if __name__ == "__main__":
    r = Adder()
    r.start()
