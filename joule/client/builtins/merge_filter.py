from joule.client import FilterModule
import textwrap
import numpy as np
from typing import Dict, List
from joule import Pipe
from joule.errors import ApiError
from scipy.interpolate import interp1d

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

        # ---- VERIFY PARAMETERS and STREAM FORMATS -----
        if master_name not in inputs:
            raise Exception("the specified master [%s] is not in the inputs" % parsed_args.master)
        master = inputs[master_name]
        slaves = [inputs[name] for name in inputs.keys() if name != master_name]
        if len(outputs) != 1:
            raise Exception("must specify one output stream")
        output = list(outputs.values())[0]
        input_width = np.sum([slave.width for slave in slaves]) + master.width
        if input_width != output.width:
            raise Exception("output must have %d elements" % input_width)
        # ---- END VERIFY ------

        if not await align_streams(master, slaves):
            return
        while not self.stop_requested:
            try:
                master_data = await master.read()
                # allocate the output array (we won't have any *more* data than this)
                output_data = np.empty(len(master_data), dtype=output.dtype)
                # put in the master data and the timestamps
                output_data['timestamp'] = master_data['timestamp']
                output_data['data'][:, :master.width] = make2d(master_data['data'])
                valid_rows = len(output_data)
                offset = master.width
                for slave in slaves:
                    valid_rows = min(await get_data(slave, output_data, offset),
                                     valid_rows)
                    offset += slave.width
                # consume the right amount from each slave based on the last valid timestamp
                for slave in slaves:
                    await consume_data(slave, output_data['timestamp'][valid_rows - 1])

                # write the output
                await output.write(output_data[:valid_rows])

                # consume the used data and check for interval breaks
                interval_break = False
                master.consume(valid_rows)

                # stay within the same interval until all streams catch up
                if master.end_of_interval and len(master_data) > valid_rows:
                    master.reread_last()
                    master.interval_break = False

                if master.end_of_interval:
                    interval_break = True
                for slave in slaves:
                    if slave.end_of_interval:
                        interval_break = True
                if interval_break:
                    await output.close_interval()
                    if not await align_streams(master, slaves):
                        break


            except ApiError:
                break
        await output.close()


def make2d(arr: np.ndarray) -> np.ndarray:
    if len(arr.shape) == 1:
        return arr[:, None]
    else:
        return arr


async def align_streams(master: Pipe, slaves: List[Pipe]):
    # we need a previous sample of every slave
    try:
        slave_datas = [await slave.read() for slave in slaves]
        master_data = await master.read()

        # get the maximum slave start time (we can't interpolate before this)
        latest_slave_start = np.max([data['timestamp'][0] for data in slave_datas])
        # make sure all streams have some data larger than the latest_slave_start
        while master_data['timestamp'][-1] < latest_slave_start:
            master.consume(len(master_data))
            master_data = await master.read()
        for i in range(len(slaves)):
            while slave_datas[i]['timestamp'][-1] < latest_slave_start:
                slaves[i].consume(len(slave_datas[i]))
                slave_datas[i] = await slaves[i].read()
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

        # to preserve any interval breaks, reread the same data again
        master.reread_last()
        for slave in slaves:
            slave.reread_last()
    except ApiError:
        return False
    return True


async def get_data(source_pipe: Pipe, dest: np.ndarray, offset: int) -> float:
    source = await source_pipe.read()
    ts = dest['timestamp']
    max_ts = source['timestamp'][-1]
    f = interp1d(source['timestamp'], source['data'], axis=0, fill_value='extrapolate')
    resampled_data = f(ts[ts <= max_ts])
    dest['data'][:len(resampled_data), offset:offset + source_pipe.width] = make2d(resampled_data)
    last_valid_ts = ts[len(resampled_data) - 1]
    dest_rows = np.argwhere(ts == last_valid_ts)[0][0] + 1
    return dest_rows


async def consume_data(source_pipe: Pipe, ts: int) -> None:
    # return
    source_pipe.reread_last()
    source = await source_pipe.read()
    used_rows = len(source['timestamp'][source['timestamp'] <= ts])
    source_pipe.consume(used_rows)
    # stay within the same interval until all streams catch up
    if source_pipe.end_of_interval and used_rows < len(source):
        source_pipe.reread_last()
        source_pipe.interval_break = False


def main():  # pragma: no cover
    r = MergeFilter()
    r.start()


if __name__ == "__main__":
    main()
