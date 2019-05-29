import click
from typing import List, Tuple, Optional, Union
from operator import attrgetter
import aiohttp
import asyncio
import json
import numpy as np
import datetime

from joule.cli.config import pass_config
from joule.api import get_node, BaseNode
from joule.models import stream, Stream, pipes, StreamInfo
from joule.utilities import interval_difference, human_to_timestamp
from joule import errors

Interval = Tuple[int, int]


@click.command(name="copy")
@click.option('-s', "--start", help="timestamp or descriptive string")
@click.option('-e', "--end", help="timestamp or descriptive string")
@click.option('-d', '--destination-node', help="node name or Nilmdb URL")
@click.option('--source-url', help="copy from a Nilmdb URL")
@click.argument("source")
@click.argument("destination")
@pass_config
def data_copy(config, start, end, destination_node, source_url, source, destination):
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(_run(config, start, end, destination_node,
                                     source_url, source, destination))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        loop.run_until_complete(
            config.close_node())
        loop.close()


async def _run(config, start, end, destination_node, source_url, source, destination):
    # determine if the source node is NilmDB or Joule
    if source_url is None:
        source_node = config.node
        nilmdb_source = False
    else:
        source_node = source_url
        await _validate_nilmdb_url(source_node)
        nilmdb_source = True

    # determine if the destination node is NilmDB or Joule
    nilmdb_dest = False

    try:
        if destination_node is None:
            dest_node = config.node
        else:
            dest_node = get_node(destination_node)
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
    # compute the target intervals (source - dest)
    src_intervals = await _get_intervals(source_node, src_stream, source, start, end, is_nilmdb=nilmdb_source)
    dest_intervals = await _get_intervals(dest_node, dest_stream, destination, start, end, is_nilmdb=nilmdb_dest)
    new_intervals = interval_difference(src_intervals, dest_intervals)
    if len(new_intervals) == 0:
        click.echo("Nothing to copy")
        return

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

    async def _copy_interval(istart, iend, bar):
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
                                yield data.tostring()
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
        await _copy(new_intervals)
        click.echo("OK")
    # this should be caught by the stream info requests
    # it is only generated if the joule server stops during the
    # data read/write
    except aiohttp.ClientError as e:  # pragma: no cover
        raise click.ClickException("Error: %s" % str(e))


async def _get_intervals(server: Union[BaseNode, str], my_stream: Stream, path: str,
                         start: Optional[int], end: Optional[int],
                         is_nilmdb: bool = False) -> List[Interval]:
    if is_nilmdb:
        intervals = []
        params = {"path": path}
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


async def _retrieve_source(server: Union[BaseNode, str], path: str, is_nilmdb: bool = False) -> Stream:
    if is_nilmdb:
        src_stream, src_info = await _retrieve_nilmdb_stream(server, path)
        if src_stream is None:
            raise errors.ApiError("The stream [%s] is not available on [%s]" % (path, server))
    else:
        src_stream = await server.stream_get(path)
        src_info = await server.stream_info(path)

    if src_info.start is None or src_info.end is None:
        raise errors.ApiError("[%s] has no data" % path)
    return src_stream


async def _retrieve_destination(server: Union[str, BaseNode], path: str, template: Stream,
                                is_nilmdb: bool = False) -> Stream:
    if is_nilmdb:
        dest_stream, dest_info = await _retrieve_nilmdb_stream(server, path)
        if dest_stream is None:
            return await _create_nilmdb_stream(server, path, template)
        else:
            return dest_stream
    else:
        try:
            return await server.stream_get(path)
        except errors.ApiError as e:
            if "404" in str(e):
                return await _create_joule_stream(server, path, template)
            raise e


async def _create_joule_stream(node: BaseNode, path: str, template: Stream) -> Stream:
    click.echo("creating destination stream")
    # split the destination into the path and stream name
    dest_stream = stream.from_json(template.to_json())
    dest_stream.keep_us = Stream.KEEP_ALL
    dest_stream.name = path.split("/")[-1]
    folder = "/".join(path.split("/")[:-1])
    return await node.stream_create(dest_stream, folder)


async def _create_nilmdb_stream(server: str, path: str, template: Stream):
    click.echo("creating destination stream")
    dest_stream = stream.from_json(template.to_json())
    dest_stream.keep_us = Stream.KEEP_ALL
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


async def _retrieve_nilmdb_stream(server: str, path: str) -> Tuple[Optional[Stream], Optional[StreamInfo]]:
    url = "{server}/stream/get_metadata".format(server=server)
    params = {"path": path, "key": json.dumps(['config_key__'])}
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
                config_data = json.loads(metadata['config_key__'])
                if config_data['name'] == '':
                    # use the path name unless there is a specifically configured value
                    config_data['name'] = path.split("/")[-1]
            except (KeyError, ValueError):
                # missing or corrupt configuration data
                pass

        # now get the stream info data
        url = "{server}/stream/list".format(server=server)
        params = {"path": path, "extended": '1'}
        async with session.get(url, params=params) as resp:

            info = (await resp.json())[0]
            my_stream = stream.from_nilmdb_metadata(config_data, info[1])
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
