from joule.client.filter import FilterModule
import numpy as np


class MeanFilter(FilterModule):
    "Compute the moving average of the input"

    def __init__(self):
        super(MeanFilter, self).__init__("Mean Filter")

    def description(self):
        return "compute moving average"

    def help(self):
        return """
        This is a filter that computes the element-wise
        moving average of the input stream.
        Specify the windown length
        Example:
            joule filter mean 4 #moving avg of last 4 samples
        """
    
    def custom_args(self, parser):
        parser.add_argument("window", type=int,
                            help="window length")
        
    def runtime_help(self, parsed_args):
        return "moving average filter with a window size of %d" % parsed_args.window

    async def run(self, parsed_args, inputs, outputs):
        stream_in = inputs["input"]
        stream_out = outputs["output"]
        data = await stream_in.read()
        print("Starting moving average filter with window size %d"
              % parsed_args.window)
        # some moving average filter
        await stream_out.write(data)
        stream_in.consume(len(data))
        
                
if __name__ == "__main__":
    r = MeanFilter()
    r.start()
