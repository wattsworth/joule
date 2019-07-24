from joule.client import ReaderModule
from joule import utilities
import textwrap
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
    $> joule-file-reader --timestamps=yes --file=/tmp/file
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
    exec_cmd = joule-file-reader

    [Arguments]
    timestamps = yes 
    file = /absolute/file/path

    [Outputs]
    output = /path/to/output
---
"""


class FileReader(ReaderModule):
    """Read data from a file"""

    def custom_args(self, parser):  # pragma: no cover
        grp = parser.add_argument_group("module",
                                        "module specific arguments")

        grp.add_argument("file", help="file name")
        grp.add_argument("-d", "--delimiter", default=",",
                         choices=[" ", ","],
                         help="character between values")
        grp.add_argument("-t", "--timestamp", type=utilities.yesno,
                         help="apply timestamps to data")
        parser.description = textwrap.dedent(ARGS_DESC)

    async def run(self, parsed_args, output):
        with open(parsed_args.file, 'r') as f:
            for line in f:
                data = np.fromstring(line, dtype=float,
                                     sep=parsed_args.delimiter)

                if parsed_args.timestamp:
                    data = np.insert(data, 0, utilities.time_now())
                await output.write(np.array([data]))
                await asyncio.sleep(0.1)
                if self.stop_requested:
                    break


def main():  # pragma: no cover
    r = FileReader()
    r.start()


if __name__ == "__main__":
    main()
