#!/usr/bin/python3

from joule.client import FilterModule


class Adder(FilterModule):
    " Add DC offset to input "

    def __init__(self):
        super(Adder, self).__init__("Adder")
    
    def custom_args(self, parser):
        parser.add_argument("offset", type=int, default=0,
                            help="apply an offset")
        
    async def run(self, parsed_args, inputs, outputs):
        stream_in = inputs["input"]
        stream_out = outputs["output"]
        while(1):
            sarray = await stream_in.read()
            sarray["data"] += parsed_args.offset
            await stream_out.write(sarray)
            stream_in.consume(len(sarray))
            

if __name__ == "__main__":
    r = Adder()
    r.start()
