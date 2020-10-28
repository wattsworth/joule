import click
import asyncio
import signal

from joule.cli.config import pass_config
from joule.models.pipes import EmptyPipe
from joule.api.data import (data_subscribe,
                            data_read)
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
    if show_bounds and elements is not None:
        raise click.ClickException("cannot do both show bounds and select elements")
    if elements is not None:
        try:
            element_indices = [int(e) for e in elements.split(',')]
        except ValueError:
            raise click.ClickException("specify elements as a comma separated like 1,4,8")
    else:
        element_indices = None

    # ---- HDF5 Output ----
    if file is not None:
        hdf = h5py.File(file, "w")
    else:
        hdf = None
    loop = asyncio.get_event_loop()

    async def _run():
        nonlocal element_indices
        if live:
            pipe = await config.node.data_subscribe(stream)
        else:
            pipe = await config.node.data_read(stream, start, end, max_rows)
        # make sure the element indices make sense with the actual data type
        if element_indices is not None and (max(element_indices) > pipe.width - 1):
            raise click.ClickException("Maximum element is %d" % (pipe.width - 1))
        dataset = None
        try:
            while not stop_requested:
                try:
                    data = await asyncio.wait_for(pipe.read(flatten=True), 1)
                    pipe.consume(len(data))
                    if element_indices is not None:
                        data_width = len(element_indices)+1
                    else:
                        data_width = pipe.width+1
                    if hdf is not None:
                        if dataset is None:
                            dataset = hdf.create_dataset(pipe.name, (len(data), data_width),
                                                         maxshape=(None, data_width),dtype='f8',
                                                         compression='gzip')
                            stream_obj = await config.node.stream_get(stream)
                            elements = stream_obj.elements
                            if element_indices is not None:
                                selected_elements = [elements[idx] for idx in element_indices]
                            else:
                                selected_elements = elements
                            element_json = {}
                            for e in selected_elements:
                                element_json[e.name] = {'units': e.units,
                                                        'offset': e.offset,
                                                        'scale_factor': e.scale_factor}
                            dataset.attrs['node_name'] = config.node.name
                            dataset.attrs['node_url'] = config.node.url
                            dataset.attrs['path'] = stream
                            dataset.attrs['elements'] = json.dumps([e.name for e in selected_elements])
                            dataset.attrs['element_info'] =json.dumps(element_json)
                            if element_indices is not None:
                                target_indices = [0] + [idx+1 for idx in element_indices]
                                dataset[...] = data[:, target_indices]
                            else:
                                dataset[...] = data
                        else:
                            cur_size = len(dataset)
                            dataset.resize((cur_size + len(data), data_width))
                            if element_indices is not None:
                                dataset[cur_size:, :] = data[:, element_indices]
                            else:
                                dataset[cur_size:, :] = data
                        continue

                    ts = data[:, 0]
                    data = data[:, 1:]
                except asyncio.TimeoutError:
                    # check periodically for Ctrl-C (SIGTERM) even if server is slow
                    continue
                if pipe.decimated and not show_bounds:
                    # suppress the bound information
                    ncols = (data.shape[1]) // 3
                    data = data[:, :ncols]
                for i in range(len(data)):
                    row = data[i]
                    if element_indices is not None:
                        selected_elements = row[element_indices]
                    else:
                        selected_elements = row
                    line = "%d %s" % (ts[i], ' '.join('%f' % x for x in selected_elements))
                    click.echo(line)
                if pipe.end_of_interval and mark_intervals:
                    click.echo("# interval break")
        except EmptyPipe:
            pass
        await pipe.close()
        if dataset is not None:
            print("Wrote [%d] rows of data" % len(dataset))
        if hdf is not None:
            hdf.close()

    try:
        loop.run_until_complete(_run())
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        loop.run_until_complete(
            config.close_node())
        loop.close()


def handler(signum, frame):
    global stop_requested
    stop_requested = True
