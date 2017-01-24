from joule.utils.time import now as time_now
from joule.client import ReaderModule
import numpy as np
import asyncio


class FileReader(ReaderModule):
    "Read data from a file"

    def __init__(self):
        super(FileReader, self).__init__("Random Reader")
        self.stop_requested = False
        self.description = "read data from a file"
        self.help = """
This is a module that reads data from a file
Specify -t to add timestamps to data (note, this should only be
used for real time FIFO's. The 8us difference in example below
is the actual time taken to read the file line)

Example:
    $> echo -e "3,4\n5,6" > /tmp/file
    $> joule reader file -t /tmp/file
    1485274825371860 3.0 4.0
    1485274825371968 5.0 6.0
"""

    def custom_args(self, parser):
        parser.add_argument("file", help="file name")
        parser.add_argument("-d", "--delimiter", default=",",
                            choices=[" ", ","],
                            help="character between values")
        parser.add_argument("-t", "--timestamp", action="store_true",
                            help="apply timestamps to data")

    async def run(self, parsed_args, output):
        with open(parsed_args.file, 'r') as f:
            for line in f:
                data = np.fromstring(line, dtype=float,
                                     sep=parsed_args.delimiter)
                if(parsed_args.timestamp):
                    data = np.insert(data, 0, time_now())
                await output.write([data])

                
if __name__ == "__main__":
    r = FileReader()
    r.start()
    
"""
            reader = asyncio.StreamReader()
            reader_protocol = asyncio.StreamReaderProtocol(reader)
            loop = asyncio.get_event_loop()
            await loop.connect_read_pipe(lambda: reader_protocol, f)
            while(True):
                line = await reader.readline()
"""
