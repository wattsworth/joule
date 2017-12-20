import numpy as np
import argparse
import joule

ARGS_DESC = """
Computes the moving average of the input stream
Specify the window length (must be odd)

Inputs:
input: N elements

Outputs:
output: N elements
"""


class MeanFilter(joule.FIRFilter):
    "Compute the moving average of the input"
    
    def custom_args(self, parser):
        parser.add_argument("window", type=int,
                            help="window length (odd)")
        parser.description = ARGS_DESC
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

    def make_filter(self, parsed_args):
        N = parsed_args.window
        return np.ones((N,))/N,

    
if __name__ == "__main__":
    r = MeanFilter()
    r.start()
