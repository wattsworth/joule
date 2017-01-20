from joule.utils.time import now as time_now
from joule.client.reader import ReaderModule
import numpy as np
import asyncio


class FileReader(ReaderModule):
    "Read data from a file"

    def __init__(self):
        super(FileReader, self).__init__("Random Reader")
        self.stop_requested = False

    def description(self):
        return "read data from a file"

    def help(self):
        return """
        This is a module that reads data from a file
        Specify -t to add timestamps to data
        Example:
            $> joule reader file /tmp/my_fifo
            1234 45 82 -33
            1234 45 82 -33
            1234 45 82 -33
            1234 45 82 -33
            1234 45 82 -33
        """

    def custom_args(self, parser):
        parser.add_argument("-f", "--file", required=True,
                            help="file name")
        parser.add_argument("-d", "--delimiter", default=",",
                            choices=[" ", ","],
                            help="character between values")
        parser.add_argument("-t", "--timestamp", action="store_true",
                            help="apply timestamps to data")

    async def run(self, parsed_args, output):
        with open(parsed_args.file, 'r') as f:
            for line in f:
                #if not line:
                #    break
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
