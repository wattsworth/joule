import numpy as np
import joule

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


class FileReader(joule.ReaderModule):
    "Read data from a file"

    def custom_args(self, parser):
        grp = parser.add_argument_group("module",
                                        "module specific arguments")

        grp.add_argument("--file",
                         required=True,
                         help="file name")
        grp.add_argument("--delimiter", default=",",
                         choices=[" ", ","],
                         help="character between values")
        grp.add_argument("--timestamp", type=joule.yesno,
                         help="apply timestamps to data")
        parser.description = ARGS_DESC
        
    async def run(self, parsed_args, output):
        with open(parsed_args.file, 'r') as f:
            for line in f:
                data = np.fromstring(line, dtype=float,
                                     sep=parsed_args.delimiter)
                if(parsed_args.timestamp):
                    data = np.insert(data, 0, joule.time_now())
                await output.write([data])
                if(self.stop_requested):
                    break

                
def main():
    r = FileReader()
    r.start()

    
if __name__ == "__main__":
    main()
