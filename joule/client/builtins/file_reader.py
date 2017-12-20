from joule.utils.time import now as time_now
from joule.client import ReaderModule
import numpy as np
import asyncio

ARGS_DESC = """
This is a module that reads data from a file
Specify -t to add timestamps to data (note, this should only be
used for real time FIFO's. The 8us difference in example below
is the actual time taken to read the file line)

Example:
    $> echo -e "3,4\n5,6" > /tmp/file
    $> joule reader file -t /tmp/file
    1485274825371860 3.0 4.0
    1485274825371868 5.0 6.0

"""


class FileReader(ReaderModule):
    "Read data from a file"

    def custom_args(self, parser):
        parser.add_argument("file", help="file name")
        parser.add_argument("-d", "--delimiter", default=",",
                            choices=[" ", ","],
                            help="character between values")
        parser.add_argument("-t", "--timestamp", action="store_true",
                            help="apply timestamps to data")
        parser.description = ARGS_DESC
        
    async def run(self, parsed_args, output):
        with open(parsed_args.file, 'r') as f:
            for line in f:
                data = np.fromstring(line, dtype=float,
                                     sep=parsed_args.delimiter)
                if(parsed_args.timestamp):
                    data = np.insert(data, 0, time_now())
                await output.write([data])
                if(self.stop_requested):
                    break

                
if __name__ == "__main__":
    r = FileReader()
    r.start()
