from joule.utils.time import now as time_now
from joule.client import ReaderModule
import numpy as np
import asyncio

ARGS_DESC = """
---
:name:
  File Reader
:author:
  John Donnal
:license:
  Open
:url:
  http://git.wattsworth.net/wattsworth/joule.git
:description:
  read data from file or named pipe
:usage:
  Read data in from a file or a named pipe.
  Optionally add timestamps to data (note, this should only be
  used for real time sources. The 8us difference in example below
  is the actual time taken to read the file line)

  Example:

  ```
    $> cat /tmp/file
    3 4
    4 6
    $> joule-file-reader --timestamps=yes /tmp/file
    1485274825371860 3.0 4.0
    1485274825371868 5.0 6.0
  ```
:inputs:
  None

:outputs:
  output
  :  float32 with N elements auto detected from input source

:stream_configs:
  #output#
     [Main]
     name = File Data
     path = /path/to/output
     datatype = float32
     keep = 1w

     # [width] number of elements
     [Element1]
     name = Data Column 1

     [Element2]
     name = Data Column 2

     #additional elements...

:module_config:
    [Main]
    name = Random Reader
    exec_cmd = joule-file-reader /name/of/file

    [Arguments]
    timestamps = yes # [yes|no]

    [Outputs]
    output = /path/to/output
---
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

                
def main():
    r = FileReader()
    r.start()

    
if __name__ == "__main__":
    main()