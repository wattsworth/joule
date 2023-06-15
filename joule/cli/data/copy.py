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
@click.option('-d', '--destination-node', help="node name or Nilmdb URL")
@click.option('--source-url', help="copy from a Nilmdb URL")
@click.argument("source")
@click.argument("destination")
@pass_config
def data_copy(config, start, end, new, destination_node, source_url, source, destination):
    """Copy data between two streams."""
    try:
        asyncio.run(_run(config.node, start, end, new, destination_node,
                                     source, destination, source_url))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        asyncio.run(
            config.close_node())


async def _run(config_node, start, end, new, destination_node, source, destination, source_url=None):
    # determine if the source node is NilmDB or Joule
    if source_url is None:
        source_node = config_node
        nilmdb_source = False
    else:
        source_node = source_url
        await _validate_nilmdb_url(source_node)
        nilmdb_source = True

    # determine if the destination node is NilmDB or Joule
    nilmdb_dest = False

    try:
        if destination_node is None:
            dest_node = config_node
        elif type(destination_node) is str:
            dest_node = get_node(destination_node)
        else:
            dest_node = destination_node
    except errors.ApiError:
        nilmdb_dest = True
        dest_node = destination_node
        await _validate_nilmdb_url(dest_node)

    # retrieve the source stream
    src_stream = await _retrieve_source(source_node, source, is_nilmdb=nilmdb_source)

    # retrieve the destination stream (create it if necessary)
    dest_stream = await _retrieve_destination(dest_node, destination, src_stream, is_nilmdb=nilmdb_dest)
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
        dest_intervals = await _get_intervals(dest_node, dest_stream, destination, None, None, is_nilmdb=nilmdb_dest)
        if len(dest_intervals) > 0:
            start = dest_intervals[-1][-1]
            print("Starting copy at [%s]" % timestamp_to_human(start))
        else:
            print("Starting copy at beginning of source")
    # compute the target intervals (source - dest)
    src_intervals = await _get_intervals(source_node, src_stream, source, start, end, is_nilmdb=nilmdb_source)
    dest_intervals = await _get_intervals(dest_node, dest_stream, destination, start, end, is_nilmdb=nilmdb_dest)
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
        if nilmdb_source:
            src_annotations = await _get_nilmdb_annotations(source_node, source, istart, iend)
        else:
            src_annotations = await source_node.annotation_get(src_stream.id, start=istart, end=iend)

        if nilmdb_dest:
            # get *all* the destination annotations, otherwise we'll loose annotations outside this interval
            dest_annotations = await _get_nilmdb_annotations(dest_node, destination)
            new_annotations = [a for a in src_annotations if a not in dest_annotations]
            if len(new_annotations) > 0:
                # create ID's for the new annotations
                if len(dest_annotations) > 0:
                    id_val = max([a.id for a in dest_annotations]) + 1
                else:
                    id_val = 0
                for a in new_annotations:
                    a.id = id_val
                    id_val += 1
                await _create_nilmdb_annotations(dest_node, destination, new_annotations + dest_annotations)
        else:
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
        if not nilmdb_dest:
            await dest_node.close()
        if not nilmdb_source:
            await source_node.close()
        return

    async def _copy_interval(istart, iend, bar):
        #print("[%s] -> [%s]" % (timestamp_to_human(istart), timestamp_to_human(iend)))
        if nilmdb_source:
            src_params = {'path': source, 'binary': 1,
                          'start': istart, 'end': iend}
            src_url = "{server}/stream/extract".format(server=source_node)
            src_headers = {}
            src_ssl = None
        else:
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
                    try:
                        while True:
                            data = await pipe.read()
                            pipe.consume(len(data))
                            if len(data) > 0:
                                cur_ts = data[-1]['timestamp']
                                yield data.tobytes()
                                # total time extents of this chunk
                                bar.update(cur_ts - last_ts)
                                last_ts = cur_ts
                            # if pipe.end_of_interval:
                            #    yield pipes.interval_token(dest_stream.layout). \
                            #        tostring()
                    except pipes.EmptyPipe:
                        pass
                    bar.update(iend - last_ts)

                if nilmdb_dest:
                    dst_params = {"start": istart, "end": iend, "path": destination, "binary": 1}
                    dst_url = "{server}/stream/insert".format(server=dest_node)
                    await _send_nilmdb_data(dst_url,
                                            dst_params, _data_sender(),
                                            pipes.compute_dtype(dest_stream.layout),
                                            session)
                else:
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
    except aiohttp.ClientError as e:  # pragma: no cover
        raise click.ClickException("Error: %s" % str(e))
    finally:
        if not nilmdb_dest:
            await dest_node.close()
        if not nilmdb_source:
            await source_node.close()


async def _get_intervals(server: Union[BaseNode, str], my_stream: DataStream, path: str,
                         start: Optional[int], end: Optional[int],
                         is_nilmdb: bool = False) -> List[Interval]:
    if is_nilmdb:
        intervals = []
        params = {"path": path}
        if start is not None:
            params['start'] = start
        if end is not None:
            params['end'] = end
        url = "{server}/stream/intervals".format(server=server)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                if not resp.status == 200:
                    raise errors.ApiError("unable to retrieve intervals for [%s]" % path)
                body = await resp.text()
                if body == '':
                    return intervals
                for line in body.strip().split("\n"):
                    intervals.append(json.loads(line))
        return intervals

    else:
        return await server.data_intervals(my_stream, start, end)


async def _retrieve_source(server: Union[BaseNode, str], path: str, is_nilmdb: bool = False) -> DataStream:
    if is_nilmdb:
        src_stream, src_info = await _retrieve_nilmdb_stream(server, path)
        if src_stream is None:
            raise errors.ApiError("The stream [%s] is not available on [%s]" % (path, server))
    else:
        src_stream = await server.data_stream_get(path)
        src_info = await server.data_stream_info(path)

    if src_info.start is None or src_info.end is None:
        raise errors.ApiError("[%s] has no data" % path)
    return src_stream


async def _retrieve_destination(server: Union[str, BaseNode], path: str, template: DataStream,
                                is_nilmdb: bool = False) -> DataStream:
    if is_nilmdb:
        dest_stream, dest_info = await _retrieve_nilmdb_stream(server, path)
        if dest_stream is None:
            return await _create_nilmdb_stream(server, path, template)
        else:
            return dest_stream
    else:
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


async def _create_nilmdb_stream(server: str, path: str, template: DataStream):
    click.echo("\tcreating destination stream")
    dest_stream = data_stream.from_json(template.to_json())
    dest_stream.keep_us = DataStream.KEEP_ALL
    dest_stream.name = path.split("/")[-1]

    url = "{server}/stream/create".format(server=server)
    data = {"path": path,
            "layout": dest_stream.layout}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data) as resp:
            if not resp.status == 200:
                raise click.ClickException("cannot create [%s] on [%s]" % (path, server))

        # add the metadata
        url = "{server}/stream/set_metadata".format(server=server)
        data = {
            "path": path,
            "data": json.dumps({"config_key__": json.dumps(dest_stream.to_nilmdb_metadata())})
        }
        async with session.post(url, data=data) as resp:
            if not resp.status == 200:
                raise click.ClickException("cannot create metadata for [%s] on [%s]" % (path, server))
    return dest_stream


async def _retrieve_nilmdb_stream(server: str, path: str) -> Tuple[Optional[DataStream], Optional[StreamInfo]]:
    url = "{server}/stream/get_metadata".format(server=server)
    params = {"path": path, "key": 'config_key__'}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            if resp.status == 404:
                return None, None
            if not resp.status == 200:
                raise errors.ApiError("[%s]: %s" % (server, resp.text))
            default_name = path.split("/")[-1]
            config_data = {'name': default_name}
            try:
                metadata = await resp.json()
                config_data = {**config_data, **(json.loads(metadata['config_key__']))}
            except (KeyError, ValueError):
                # missing or corrupt configuration data
                pass

        # now get the stream info data
        url = "{server}/stream/list".format(server=server)
        params = {"path": path, "extended": '1'}
        async with session.get(url, params=params) as resp:

            info = (await resp.json())[0]
            my_stream = data_stream.from_nilmdb_metadata(config_data, info[1])
            my_info = StreamInfo(start=info[2],
                                 end=info[3],
                                 rows=info[4],
                                 bytes=-1,  # signal that this field is invalid
                                 total_time=info[5])
            return my_stream, my_info


async def _send_nilmdb_data(url, params, generator, dtype, session):
    bstart = params['start']
    async for data in generator:
        params['start'] = bstart
        np_data = np.frombuffer(data, dtype)
        bend = int(np_data['timestamp'][-1] + 1)
        params['end'] = bend

        async with session.put(url,
                               params=params,
                               data=data) as dest_response:
            if dest_response.status != 200:
                msg = await dest_response.text()
                raise errors.ApiError("Error writing to destination: %s" % msg)
        bstart = bend


async def _validate_nilmdb_url(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            body = await resp.text()
            if 'NilmDB' not in body:
                raise errors.ApiError("[%s] is not a Nilmdb server" % url)


# save retrieved annotations so we don't make extra network requests
# there is no interval retrieval mechanism for NilmDB annotations
cached_nilmdb_annotations: Dict[str, List[Annotation]] = {}


async def _get_nilmdb_annotations(server: str, path: str, istart: Optional[int] = None, iend: Optional[int] = None) -> List[Annotation]:
    url = "{server}/stream/get_metadata".format(server=server)
    params = {"path": path, "key": '__annotations'}
    global cached_nilmdb_annotations
    if path in cached_nilmdb_annotations:
        annotations = cached_nilmdb_annotations[path]
        if istart is None or iend is None:
            return annotations
        return [a for a in annotations if istart <= a.start <= iend]

    annotations = []
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            if resp.status == 404:
                return []
            if not resp.status == 200:
                raise errors.ApiError("[%s]: %s" % (server, resp.text))
            try:
                metadata = await resp.json()
                if metadata['__annotations'] is not None:
                    annotation_data = json.loads(metadata['__annotations'])
                    for item in annotation_data:
                        item['stream_id'] = None
                        annotations.append(annotation_from_json(item))
            except (KeyError, ValueError):
                # missing or corrupt annotation data
                pass
    cached_nilmdb_annotations[path] = annotations
    # only return annotations within the requested interval
    if istart is None or iend is None:
        return annotations
    return [a for a in annotations if istart <= a.start <= iend]


async def _create_nilmdb_annotations(server: str, path: str, annotations: List[Annotation]) -> None:
    # create the JSON data
    annotation_json = [a.to_json() for a in annotations]
    data = {"__annotations": json.dumps(annotation_json)}
    url = "{server}/stream/update_metadata".format(server=server)
    data = {"path": path,
            "data": json.dumps(data)}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data) as resp:
            if not resp.status == 200:
                raise click.ClickException("cannot create metadata for [%s] on [%s]" % (path, server))
