import click
import asyncio
import signal

from joule.cli.config import pass_config
from joule.models.pipes import EmptyPipe

import h5py
import json
from joule import errors
from joule.utilities import human_to_timestamp

stop_requested = False


@click.command(name="read")
@click.option('-s', "--start", help="timestamp or descriptive string")
@click.option('-e', "--end", help="timestamp or descriptive string")
@click.option('-l', "--live", is_flag=True, help="subscribe to an active stream")
@click.option('-r', "--max-rows", help="limit response data", type=int)
@click.option('-b', "--show-bounds", is_flag=True, help="include min/max for decimated data")
@click.option('-m', "--mark-intervals", help="include [# interval break] tags", is_flag=True)
@click.option('-i', "--elements", help="only include specified elements (first element is 0)")
@click.option('-f', "--file", help="write output to file in hdf5 format")
@click.argument("stream")
@pass_config
def cmd(config, start, end, live, max_rows, show_bounds, mark_intervals, elements, file, stream):
    """Read data from a stream."""
    signal.signal(signal.SIGTERM, handler)
    signal.signal(signal.SIGINT, handler)

    if live and (start is not None or end is not None):
        raise click.ClickException("specify either --live or --start/--end, not both")
    if live and max_rows is not None:
        raise click.ClickException("cannot specify --live and --max-rows")
    if start is not None:
        try:
            start = human_to_timestamp(start)
        except ValueError:
            raise click.ClickException("invalid start time: [%s]" % start)
    if end is not None:
        try:
            end = human_to_timestamp(end)
        except ValueError:
            raise click.ClickException("invalid end time: [%s]" % end)

    # ---- Element selection ----
    if elements is not None:
        try:
            element_indices = [int(e) for e in elements.split(',')]
        except ValueError:
            raise click.ClickException("specify elements as a comma separated like 1,4,8")
    else:
        element_indices = None

    # ---- HDF5 Output ----
    if file is not None:
        write_to_file = True
    else:
        write_to_file = False
    hdf_file = None


    async def _run():
        nonlocal element_indices
        nonlocal hdf_file
        nonlocal start, end
        hdf_data = None
        hdf_timestamps = None
        # progress bar for writing to a file
        bar_ctx = None
        bar = None

        # get the stream object from the API
        stream_obj = await config.node.data_stream_get(stream)
        stream_info = await config.node.data_stream_info(stream)
        if stream_info.rows == 0:
            raise click.ClickException("This stream has no data")
        if live:
            pipe = await config.node.data_subscribe(stream)
        else:
            pipe = await config.node.data_read(stream, start, end, max_rows)
        # find the actual start / end bounds of the data read
        if start is None or start < stream_info.start:
            start = stream_info.start
        if end is None or end > stream_info.end:
            end = stream_info.end
        total_time = end - start
        # make sure the element indices make sense with the actual data type
        if element_indices is not None and (max(element_indices) > pipe.width - 1):
            raise click.ClickException("Maximum element is %d" % (pipe.width - 1))
        if element_indices is None:
            element_indices = list(range(len(stream_obj.elements)))
        while not stop_requested and not pipe.is_empty():
            # get new data from the pipe
            try:
                # read structured data
                sdata = await asyncio.wait_for(pipe.read(), 1)
                pipe.consume(len(sdata))
            except asyncio.TimeoutError:
                # check periodically for Ctrl-C (SIGTERM) even if server is slow
                continue
            # ===== Write to HDF File ======
            if write_to_file:
                if len(sdata) > 0:  # ignore empty chunks
                    data_width = len(element_indices)
                    target_indices = element_indices  # [0] + [idx + 1 for idx in element_indices]
                    if hdf_file is None:
                        # create dataset and populate it with current data
                        hdf_data, hdf_timestamps, hdf_file = _create_hdf_dataset(config, stream_obj, stream,
                                                                                 element_indices,
                                                                                 file, pipe, data_width,
                                                                                 initial_size=len(sdata),
                                                                                 )
                        hdf_data[...] = sdata['data'][:, target_indices]
                        hdf_timestamps[...] = sdata['timestamp'][:, None]
                        bar_ctx = click.progressbar(length=total_time, label='reading data')
                        # print("total_time: %d" % total_time)
                        bar = bar_ctx.__enter__()
                        chunk_duration = sdata['timestamp'][-1] - sdata['timestamp'][0]
                        bar.update(chunk_duration)
                        # print(chunk_duration)
                    else:
                        # expand dataset, append new data
                        cur_size = len(hdf_data)
                        chunk_duration = sdata['timestamp'][-1] - sdata['timestamp'][0]
                        # print("[%d-%d ==> %d]" % (data[-1, 0], hdf_dataset[-1, 0], cum_time))
                        bar.update(chunk_duration)
                        hdf_data.resize((cur_size + len(sdata), data_width))
                        hdf_data[cur_size:, :] = sdata['data'][:, target_indices]
                        hdf_timestamps.resize((cur_size + len(sdata), 1))
                        hdf_timestamps[cur_size:] = sdata['timestamp'][:, None]
                        # update with the new chunk of time
                else:
                    print("ignoring empty chunk")
            # ===== Write to stdout (Terminal) ======
            else:
                ts = sdata['timestamp']
                data = sdata['data']
                if pipe.decimated:
                    if show_bounds:
                        # add the bound info
                        num_elements = len(stream_obj.elements)
                        displayed_cols = element_indices + \
                                         [idx + num_elements for idx in element_indices] + \
                                         [idx + num_elements * 2 for idx in element_indices]
                    else:
                        # suppress the bound info
                        displayed_cols = element_indices
                else:
                    displayed_cols = element_indices
                # print out each line, keeping timestamps as integers
                for i in range(len(data)):
                    row = data[i]
                    selected_data = row[displayed_cols]
                    line = "%d %s" % (ts[i], ' '.join('%f' % x for x in selected_data))
                    click.echo(line)
                if pipe.end_of_interval and mark_intervals:
                    click.echo("# interval break")

        await pipe.close()
        if bar_ctx is not None:
            bar.update(end - hdf_timestamps[-1])
            bar_ctx.__exit__(None, None, None)
        if hdf_data is not None:
            hdf_file.close()
        if hdf_timestamps is not None:
            hdf_file.close()

    try:
        asyncio.run(_run())
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        asyncio.run(
            config.close_node())


def handler(signum, frame):
    global stop_requested
    stop_requested = True


def _create_hdf_dataset(config, stream, path, element_indices, file, pipe, data_width, initial_size):
    hdf_root = h5py.File(file, "w")
    # note this could be optimized to store data in the correct datatype
    # right now everything is stored as a double which is probably excessive precision
    # but is needed for the timestamps
    hdf_data = hdf_root.create_dataset('data', (initial_size, data_width),
                                       maxshape=(None, data_width), dtype=pipe.dtype[1].base,
                                       compression='gzip')
    hdf_timestamps = hdf_root.create_dataset('timestamp', (initial_size, 1),
                                             maxshape=(None, 1), dtype='i8',
                                             compression='gzip')
    elements = stream.elements
    if element_indices is not None:
        selected_elements = [elements[idx] for idx in element_indices]
    else:
        selected_elements = elements
    element_json = [e.to_json() for e in selected_elements]
    hdf_root.attrs['node_name'] = config.node.name
    hdf_root.attrs['node_url'] = config.node.url
    hdf_root.attrs['path'] = path
    hdf_root.attrs['elements'] = json.dumps([e.name for e in selected_elements])
    hdf_root.attrs['element_json'] = json.dumps(element_json)
    return hdf_data, hdf_timestamps, hdf_root
