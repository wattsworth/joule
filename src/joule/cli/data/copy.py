import click
from typing import Dict, List, Tuple, Optional, Union
from operator import attrgetter
import aiohttp
import asyncio
import json
import numpy as np
import datetime

from joule.cli.config import pass_config
from joule.api import get_node, BaseNode, Annotation
from joule.api.annotation import from_json as annotation_from_json
from joule.models import data_stream, DataStream, pipes, StreamInfo
from joule.utilities import interval_difference, human_to_timestamp, timestamp_to_human
from joule import errors

Interval = Tuple[int, int]


@click.command(name="copy")
@click.option('-s', "--start", help="timestamp or descriptive string")
@click.option('-e', "--end", help="timestamp or descriptive string")
@click.option('-n', '--new', help="copy starts at the last timestamp of the destination", is_flag=True)
@click.option('-d', '--destination-node', help="node name")
@click.argument("source")
@click.argument("destination")
@pass_config
def data_copy(config, start, end, new, destination_node, source, destination):
    """Copy data between two streams."""
    try:
        asyncio.run(_run(config.node, start, end, new, destination_node,
                                     source, destination))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        asyncio.run(
            config.close_node())


async def _run(config_node, start, end, new, destination_node, source, destination):
    source_node = config_node
    
    try:
        if destination_node is None:
            dest_node = config_node
        elif type(destination_node) is str:
            dest_node = get_node(destination_node)
        else:
            dest_node = destination_node
    except errors.ApiError:
        raise click.ClickException("Error: cannot connect to destination node [%s]" % destination_node)

    # retrieve the source stream
    src_stream = await _retrieve_source(source_node, source)

    # retrieve the destination stream (create it if necessary)
    dest_stream = await _retrieve_destination(dest_node, destination, src_stream)
    # make sure streams are compatible
    if src_stream.layout != dest_stream.layout:
        raise errors.ApiError("Error: source (%s) and destination (%s) datatypes are not compatible" % (
            src_stream.layout, dest_stream.layout))
    # warn if the elements are not the same
    element_warning = False
    src_elements = sorted(src_stream.elements, key=attrgetter('index'))
    dest_elements = sorted(dest_stream.elements, key=attrgetter('index'))
    for i in range(len(src_elements)):
        if src_elements[i].name != dest_elements[i].name:
            element_warning = True
        if src_elements[i].units != dest_elements[i].units:
            element_warning = True
    if (element_warning and
            not click.confirm("WARNING: Element configurations do not match. Continue?")):
        click.echo("Cancelled")
        return
    # if new is set start and end may not be specified
    if new and start is not None:
        raise click.ClickException("Error: either specify 'new' or a starting timestamp, not both")

    # make sure the time bounds make sense
    if start is not None:
        try:
            start = human_to_timestamp(start)
        except ValueError:
            raise errors.ApiError("invalid start time: [%s]" % start)
    if end is not None:
        try:
            end = human_to_timestamp(end)
        except ValueError:
            raise errors.ApiError("invalid end time: [%s]" % end)
    if (start is not None) and (end is not None) and ((end - start) <= 0):
        raise click.ClickException("Error: start [%s] must be before end [%s]" % (
            datetime.datetime.fromtimestamp(start / 1e6),
            datetime.datetime.fromtimestamp(end / 1e6)))
    if new:
        # pull all the destination intervals and use the end of the last one as the 'end' for the copy
        dest_intervals = await dest_node.data_intervals(dest_stream, start=None, end=None)
        if len(dest_intervals) > 0:
            start = dest_intervals[-1][-1]
            print("Starting copy at [%s]" % timestamp_to_human(start))
        else:
            print("Starting copy at beginning of source")
    # compute the target intervals (source - dest)
    src_intervals = await source_node.data_intervals(src_stream, start, end)
    dest_intervals = await dest_node.data_intervals(dest_stream, start, end)
    new_intervals = interval_difference(src_intervals, dest_intervals)
    existing_intervals = interval_difference(src_intervals, new_intervals)

    async def _copy(intervals):
        # compute the duration of data to copy
        duration = 0
        for interval in intervals:
            duration += interval[1] - interval[0]

        with click.progressbar(
                label='Copying data',
                length=duration) as bar:
            for interval in intervals:
                await _copy_interval(interval[0], interval[1], bar)
                await _copy_annotations(interval[0], interval[1])

    async def _copy_annotations(istart, iend):
        src_annotations = await source_node.annotation_get(src_stream.id, start=istart, end=iend)
        
        dest_annotations = await dest_node.annotation_get(dest_stream.id, start=istart, end=iend)
        new_annotations = [a for a in src_annotations if a not in dest_annotations]
        for annotation in new_annotations:
            await dest_node.annotation_create(annotation, dest_stream.id)

    if len(new_intervals) == 0:
        if len(src_intervals) > 0:
            click.echo("Nothing to copy, syncing annotations")
            for interval in src_intervals:
                await _copy_annotations(interval[0], interval[1])
        else:
            click.echo("Nothing to copy")
        # clean up
        await dest_node.close()
        await source_node.close()
        return

    async def _copy_interval(istart, iend, bar):
        
        src_params = {'id': src_stream.id, 'start': istart, 'end': iend}
        src_url = "{server}/data".format(server=source_node.session.url)
        src_headers = {"X-API-KEY": source_node.session.key}
        src_ssl = source_node.session.ssl_context
        async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=None)) as session:
            async with session.get(src_url,
                                   params=src_params,
                                   headers=src_headers,
                                   ssl=src_ssl) as src_response:
                if src_response.status != 200:
                    msg = await src_response.text()
                    if msg == 'this stream has no data':
                        # This is not an error because a previous copy may have been interrupted
                        # This will cause the destination to have an interval gap where the source has no data
                        # Example:   source:  |**     *******|
                        #            dest:    |** |  |*******|
                        #                          ^--- looks like missing data but there's nothing in the source
                        return  # ignore empty intervals
                    raise click.ClickException("Error reading from source: %s" % msg)

                pipe = pipes.InputPipe(stream=dest_stream, reader=src_response.content)

                async def _data_sender():

                    last_ts = istart
                    while await pipe.not_empty():
                        data = await pipe.read()
                        pipe.consume(len(data))
                        if len(data) > 0:
                            cur_ts = data[-1]['timestamp']
                            yield data.tobytes()
                            # total time extents of this chunk
                            bar.update(cur_ts - last_ts)
                            last_ts = cur_ts
                    bar.update(iend - last_ts)

               
                dst_url = "{server}/data".format(server=dest_node.session.url)
                dst_params = {"id": dest_stream.id}
                dst_headers = {"X-API-KEY": dest_node.session.key}
                dst_ssl = dest_node.session.ssl_context
                async with session.post(dst_url,
                                        params=dst_params,
                                        data=_data_sender(),
                                        headers=dst_headers,
                                        ssl=dst_ssl,
                                        chunked=True) as dest_response:
                    if dest_response.status != 200:
                        msg = await dest_response.text()
                        raise errors.ApiError("Error writing to destination: %s" % msg)

    try:
        # copy over any new annotations from existing intervals
        for interval in existing_intervals:
            await _copy_annotations(interval[0], interval[1])
        await _copy(new_intervals)
        click.echo("\tOK")
    # this should be caught by the stream info requests
    # it is only generated if the joule server stops during the
    # data read/write
    except aiohttp.ClientError as e:  
        raise click.ClickException("Error: %s" % str(e))
    finally:
        await dest_node.close()
        await source_node.close()


async def _retrieve_source(server: BaseNode | str, path: str) -> DataStream:
    src_stream = await server.data_stream_get(path)
    src_info = await server.data_stream_info(path)

    if src_info.start is None or src_info.end is None:
        raise errors.ApiError("[%s] has no data" % path)
    return src_stream


async def _retrieve_destination(server: str | BaseNode, path: str, template: DataStream) -> DataStream:
    try:
        return await server.data_stream_get(path)
    except errors.ApiError as e:
        if "404" in str(e):
            return await _create_joule_stream(server, path, template)
        raise e


async def _create_joule_stream(node: BaseNode, path: str, template: DataStream) -> DataStream:
    click.echo("\tcreating destination stream")
    # split the destination into the path and stream name
    dest_stream = data_stream.from_json(template.to_json())
    dest_stream.keep_us = DataStream.KEEP_ALL
    dest_stream.name = path.split("/")[-1]
    folder = "/".join(path.split("/")[:-1])
    return await node.data_stream_create(dest_stream, folder)