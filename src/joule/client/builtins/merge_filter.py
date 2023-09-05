from joule.client import FilterModule
import textwrap
import numpy as np
from typing import Dict, List
from joule import Pipe
from joule.errors import ApiError, EmptyPipeError
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
  Specify a primary stream and one or more additional streams.
  The output will have timestamps from the primary stream and linearly
  interpolated data from all the additional streams
  
  
    | Arguments | Description        |
    |-----------|--------------------|
    |``primary`` | name of primary stream |

  ```
:inputs:
  primary
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
    primary = input1 

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
        grp.add_argument("--primary", type=str, required=True,
                         help="name of primary input stream")
        parser.description = textwrap.dedent(ARGS_DESC)

    async def run(self, parsed_args, inputs: Dict[str, Pipe], outputs):
        primary_name = parsed_args.primary

        # ---- VERIFY PARAMETERS and STREAM FORMATS -----
        if primary_name not in inputs:
            raise Exception("the specified primary [%s] is not in the inputs" % parsed_args.primary)
        primary = inputs[primary_name]
        secondaries = [inputs[name] for name in inputs.keys() if name != primary_name]
        if len(outputs) != 1:
            raise Exception("must specify one output stream")
        output = list(outputs.values())[0]
        input_width = np.sum([secondary.width for secondary in secondaries]) + primary.width
        if input_width != output.width:
            raise Exception("output must have %d elements" % input_width)
        # ---- END VERIFY ------

        if not await align_streams(primary, secondaries):
            await output.close()  # no data overlap so nothing can be processed
            return
        while not self.stop_requested:
            try:
                primary_data = await primary.read()
                # allocate the output array (we won't have any *more* data than this)
                output_data = np.empty(len(primary_data), dtype=output.dtype)
                # put in the primary data and the timestamps
                output_data['timestamp'] = primary_data['timestamp']
                output_data['data'][:, :primary.width] = make2d(primary_data['data'])
                valid_rows = len(output_data)
                offset = primary.width
                for secondary in secondaries:
                    valid_rows = min(await get_data(secondary, output_data, offset),
                                     valid_rows)
                    offset += secondary.width
                # consume the right amount from each secondary based on the last valid timestamp
                for secondary in secondaries:
                    await consume_data(secondary, output_data['timestamp'][valid_rows - 1])

                # write the output
                await output.write(output_data[:valid_rows])

                # consume the used data and check for interval breaks
                interval_break = False
                primary.consume(valid_rows)

                # stay within the same interval until all streams catch up
                if primary.end_of_interval and len(primary_data) > valid_rows:
                    primary.reread_last()
                if primary.end_of_interval:
                    interval_break = True
                for secondary in secondaries:
                    if secondary.end_of_interval:
                        # stay within the same interval until all streams catch up
                        secondary.reread_last()
                if interval_break:
                    await output.close_interval()
                    if not await align_streams(primary, secondaries):
                        break
            except EmptyPipeError:
                break
            except Exception as e:
                await output.close()
                raise e
        await output.close()


def make2d(arr: np.ndarray) -> np.ndarray:
    if len(arr.shape) == 1:
        return arr[:, None]
    else:
        return arr


async def align_streams(primary: Pipe, secondaries: List[Pipe]):
    # we need a previous sample of every secondary
    try:
        secondary_data = [await secondary.read() for secondary in secondaries]
        primary_data = await primary.read()
        # get the maximum secondary start time (we can't interpolate before this)
        try:
            latest_secondary_start = np.max([data['timestamp'][0] for data in secondary_data])
        except IndexError as e:
            breakpoint()
            print(e)
        # make sure all streams have some data larger than the latest_secondary_start
        while primary_data['timestamp'][-1] < latest_secondary_start:
            primary.consume(len(primary_data))
            primary_data = await primary.read()
        for i in range(len(secondaries)):
            while secondary_data[i]['timestamp'][-1] < latest_secondary_start:
                secondaries[i].consume(len(secondary_data[i]))
                secondary_data[i] = await secondaries[i].read()
        # find the closest ts in primary that is larger than latest_secondary_start
        start_ts = primary_data['timestamp'][primary_data['timestamp'] >= latest_secondary_start][0]
        i = 0
        for data in secondary_data:
            # find the closest ts in secondaries that is smaller than latest_secondary_start
            idx = np.argmax(data['timestamp'][data['timestamp'] <= start_ts])
            # consume up to this point
            secondaries[i].consume(idx)
            i += 1
        # consume the primary before start_ts
        too_early = primary_data['timestamp'][primary_data['timestamp'] < start_ts]
        primary.consume(len(too_early))
        # to preserve any interval breaks, reread the same data again
        primary.reread_last()
        for secondary in secondaries:
            secondary.reread_last()
    except ApiError:
        return False
    return True


async def get_data(source_pipe: Pipe, dest: np.ndarray, offset: int) -> float:
    source = await source_pipe.read()
    ts = dest['timestamp']
    max_ts = source['timestamp'][-1]
    f = interp1d(source['timestamp'], source['data'], axis=0, fill_value='extrapolate')
    resampled_data = f(ts[ts <= max_ts])
    if len(resampled_data) == 0:
        return 0  # nothing to do
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
