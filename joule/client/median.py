from joule.client.filter import FilterModule
import numpy as np


class MedianFilter(FilterModule):
    "Compute the moving average of the input"

    def __init__(self):
        super(MedianFilter, self).__init__("Median Filter")

    def description(self):
        return "compute median"

    def help(self):
        return """
        This is a filter that computes the element-wise
        median of the input stream
        Specify the windown length
        Example:
            joule filter median 4 # 4-wide median
        """

    def custom_args(self, parser):
        parser.add_argument("window", type=int,
                            help="window length")

    def runtime_help(self, parsed_args):
        return "median filter with a window size of %d" % parsed_args.window

    async def run(self, parsed_args, inputs, outputs):
        stream_in = inputs["input"]
        stream_out = outputs["output"]
        data = await stream_in.read()
        # some median filter
        await stream_out.write(data)
        stream_in.consume(len(data))
        
                
if __name__ == "__main__":
    r = MedianFilter()
    r.start()
