from joule.client.filter import FilterModule
import numpy as np


class MergeFilter(FilterModule):
    "Merge streams by resampling"

    def __init__(self):
        super(MergeFilter, self).__init__("Merge Filter")

    def description(self):
        return "merge inputs into a single output"

    def help(self):
        return """
        This is filter merges multiple inputs into a single
        output by resampling the streams to a common timeseries.
        Specify the master input stream which will be used as the
        resample basis. Note: use the highest bandwidth stream as the
        master to avoid aliasing in the output.

        Example:
            joule filter merge sensor1 #resample to input "sensor1"
        """

    def custom_args(self, parser):
        parser.add_argument("master",
                            help="resample to this stream")

    def runtime_help(self, parsed_args):
        return "merge inputs by resampling to [%s]" % parsed_args.master

    async def run(self, parsed_args, inputs, outputs):
        assert False, "TODO: implement this filter"
        return

    
if __name__ == "__main__":
    r = MergeFilter()
    r.start()
