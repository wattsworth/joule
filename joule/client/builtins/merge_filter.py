from joule.client import FilterModule
from joule import utilities
import textwrap
import numpy as np
import asyncio
from typing import Dict, List
from joule import Pipe
from joule.errors import ApiError
from scipy.interpolate import interp1d
import pdb

ARGS_DESC = """
---
:name:
  Merge Filter
:author:
  John Donnal
:license:
  Open
:url:
  http://git.wattsworth.net/wattsworth/joule.git
:description:
  combine multiple input streams into a single output stream
:usage:
  Specify a master stream and one or more additional streams.
  The output will have timestamps from the master stream and linearly
  interpolated data from all the additional streams
  
  
    | Arguments | Description        |
    |-----------|--------------------|
    |``master`` | name of master stream |

  ```
:inputs:
  master
  : N elements
  additional
  : M elements

:outputs:
  output
  :  float32 with N+M elements auto detected from input source

:stream_configs:
  #output#
     [Main]
     name = Merged
     path = /path/to/output
     datatype = float32
     keep = 1w

     # [width] number of elements of all input streams
     [Element1]
     name = Data Column 1

     [Element2]
     name = Data Column 2

     #additional elements...

:module_config:
    [Main]
    name = Merge Filter
    exec_cmd = joule-merge-filter

    [Arguments]
    master = input1 

    [Inputs]
    input1 = /path/to/input1
    input2 = /path/to/input2
    #... additional inputs as desired
    
    [Outputs]
    output = /path/to/output
---
"""


class MergeFilter(FilterModule):
    """Merge input streams"""

    def custom_args(self, parser):  # pragma: no cover
        grp = parser.add_argument_group("module",
                                        "module specific arguments")
        grp.add_argument("--master", type=str, required=True,
                         help="name of master input stream")
        parser.description = textwrap.dedent(ARGS_DESC)

    async def run(self, parsed_args, inputs: Dict[str, Pipe], outputs):
        master_name = parsed_args.master
        if master_name not in inputs:
            raise Exception("the specified master [%s] is not in the inputs" % parsed_args.master)
        master = inputs[master_name]
        slaves = [inputs[name] for name in inputs.keys() if name != master_name]
        if len(outputs) != 1:
            raise Exception("must specify one output stream")
        output = list(outputs.values())[0]
        await align_streams(master, slaves)
        while not self.stop_requested:
            try:
                master_data = await master.read()

                slave_datas = [await slave.read() for slave in slaves]
            except ApiError:
                await output.close()
                break
            # allocate the output array (we won't have any *more* data than this)
            output_data = np.empty(len(master_data), dtype=output.dtype)
            # put in the master data and the timestamps
            output_data['timestamp'] = master_data['timestamp']
            output_data['data'][:, :num_cols(master_data)] = master_data['data']

            total_rows = len(output_data)
            offset_col = num_cols(master_data)
            for data in slave_datas:
                rows = resample(output_data, offset_col, data)
                offset_col += num_cols(data)
                total_rows = min((rows, total_rows))
            # consume the used data and check for interval breaks
            interval_break = False
            master.consume(total_rows)
            if master.end_of_interval:
                interval_break = True
            for slave in slaves:
                slave.consume(total_rows)
                if slave.end_of_interval:
                    interval_break = True
            if interval_break:
                await align_streams(master, slaves)

            # write the output
            await output.write(output_data[:total_rows])


def num_cols(arr: np.ndarray) -> int:
    return np.atleast_2d(arr['data']).shape[1]


async def align_streams(master: Pipe, slaves: List[Pipe]):
    # we need a previous sample of every slave
    slave_datas = [await slave.read() for slave in slaves]
    master_data = await master.read()
    # get the maximum slave start time (we can't interpolate before this)
    latest_slave_start = np.max([data['timestamp'][0] for data in slave_datas])
    # find the closest ts in master that is larger than latest_slave_start
    start_ts = master_data['timestamp'][master_data['timestamp'] >= latest_slave_start][0]
    i = 0
    for data in slave_datas:
        # find the closest ts in slaves that is smaller than latest_slave_start
        idx = np.argmax(data['timestamp'][data['timestamp'] <= start_ts])
        # consume up to this point
        slaves[i].consume(idx)
        i += 1
    # consume the master before start_ts
    too_early = master_data['timestamp'][master_data['timestamp'] < start_ts]
    master.consume(len(too_early))


def resample(output: np.ndarray, offset_col: int, input: np.ndarray) -> int:
    ts = output['timestamp']
    max_ts = input['timestamp'][-1]
    f = interp1d(input['timestamp'], input['data'], axis=0, fill_value='extrapolate')
    resampled_data = f(ts[ts <= max_ts])
    if len(resampled_data.shape) == 1:
        resampled_data = resampled_data[:, None]
    output['data'][:, offset_col:offset_col+num_cols(input)] = resampled_data
    return len(ts[ts <= max_ts])


def main():  # pragma: no cover
    r = MergeFilter()
    r.start()


if __name__ == "__main__":
    main()
