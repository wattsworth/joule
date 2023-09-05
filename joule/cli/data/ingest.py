import click
import asyncio
import signal

from joule.cli.config import pass_config
from joule.models.pipes import compute_dtype
from joule.api.data_stream import DataStream, Element, elem_from_json

import h5py
import json
import numpy as np
from joule import errors
from joule.utilities import timestamp_to_human
stop_requested = False

BLOCK_SIZE = 10000  # insert blocks of datta


@click.command(name="ingest")
@click.option('-f', "--file", help="read data from hd5 file")
@click.option("-s", "--stream", "stream_path", help="stream path")
@pass_config
def ingest(config, stream_path, file):
    """Add data from an HD5 file to a stream."""
    signal.signal(signal.SIGTERM, handler)
    signal.signal(signal.SIGINT, handler)


    async def _run():
        nonlocal stream_path
        # Open the file and make sure it is the right type
        try:
            hdf_root = h5py.File(file, 'r')
            hdf_timestamp = hdf_root['timestamp']
            hdf_data = hdf_root['data']
            start = hdf_timestamp[0, 0]
            end = hdf_timestamp[-1, 0]
            # make sure the length of both datasets are  the same
            if len(hdf_data) != len(hdf_timestamp):
                raise click.ClickException("Length of [data] and [timestamp] datasets must match")
            # if a stream is not specified see if one is in the data file
            if stream_path is None:
                try:
                    stream_path = hdf_root.attrs['path']
                except KeyError:
                    raise click.ClickException("Specify a target stream with --stream")
        except OSError:
            raise click.ClickException("Data file [%s] must be hdf5 format" % file)
        except KeyError:
            raise click.ClickException("Data file must contain [data] and [timestamp] datasets")

        # get the stream object from the API
        try:
            stream_obj = await config.node.data_stream_get(stream_path)
            print("Destination stream: %s" % stream_path)

            stream_info = await config.node.data_stream_info(stream_path)
            # make sure the datatypes match
            dtype = compute_dtype(stream_obj.layout)
            if dtype[1].base != hdf_data.dtype:
                raise click.ClickException("Incompatible datatypes, stream is [%s] and data file is [%s]" % (
                    (dtype[1].base, hdf_data.dtype)
                ))
            # make sure the number of elements match
            if len(stream_obj.elements) != hdf_data.shape[1]:
                raise click.ClickException("DataStream has [%d] elements but data file has [%d] elements" % (
                    len(stream_obj.elements), hdf_data.shape[1]
                ))
            # check if there is existing data in this time period
            if stream_info.rows > 0 and (
                    start < stream_info.end and end >= stream_info.start):
                # confirm overwrite
                if not click.confirm("This will remove existing data between %s- %s" % (
                        timestamp_to_human(start),
                        timestamp_to_human(end))):
                    click.echo("Cancelled")
                    return
                await config.node.data_delete(stream_obj, start, end+1)
        except errors.ApiError as e:
            if '404' not in str(e):
                raise click.ClickException(str(e))
            # this stream doesn't exist, create it from the hdf attributes
            stream_obj = await _create_stream(stream_path, hdf_root, config.node)

        pipe = await config.node.data_write(stream_obj)

        # progress bar for writing to a file
        bar_ctx = click.progressbar(length=len(hdf_data), label='ingesting data')
        bar = bar_ctx.__enter__()
        for idx in range(0, len(hdf_data), BLOCK_SIZE):
            ts = hdf_timestamp[idx:idx + BLOCK_SIZE]
            data = hdf_data[idx:idx + BLOCK_SIZE]
            sdata = np.empty(len(ts), dtype=compute_dtype(stream_obj.layout))
            sdata['timestamp'][:, None] = ts
            sdata['data'] = data
            await pipe.write(sdata)
            bar.update(len(data))
        await pipe.close()
        bar_ctx.__exit__(None, None, None)

    try:
        asyncio.run(_run())
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        asyncio.run(
            config.close_node())


async def _create_stream(stream_path, hdf_root, node):
    # try to get the elements from the hdf attrs
    try:
        element_json = json.loads(hdf_root.attrs['element_json'])
        elements = [elem_from_json(e) for e in element_json]
    except KeyError:
        # just make default elements
        num_elements = hdf_root['data'].shape[1]
        elements = [Element("Element %d" % i) for i in range(num_elements)]

    stream_name = stream_path.split('/')[-1]
    folder = '/'.join(stream_path.split('/')[:-1])
    if folder == '':
        raise click.ClickException("Invalid stream path, must include a folder")
    new_stream = DataStream(stream_name)
    new_stream.datatype = hdf_root['data'].dtype.name
    new_stream.elements = elements
    stream_obj = await node.data_stream_create(new_stream, folder)
    print("creating [%s]" % stream_path)
    return stream_obj


def _build_default_elements(num_elements):
    return [Element("Element %d" % i) for i in range(num_elements)]


def handler(signum, frame):
    global stop_requested
    stop_requested = True
