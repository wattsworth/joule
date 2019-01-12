import click
import requests
from typing import List, Tuple, Optional
from operator import attrgetter
import dateparser
import aiohttp
import asyncio
import json
import numpy as np
import datetime

from joule.cli.config import pass_config
from joule.cli.helpers import get_json, get
from joule.models import stream, Stream, pipes, StreamInfo
from joule.utilities import interval_difference
from joule.errors import ConnectionError

Interval = Tuple[int, int]


@click.command(name="copy")
@click.option('-s', "--start", help="timestamp or descriptive string")
@click.option('-e', "--end", help="timestamp or descriptive string")
@click.option('-U', '--dest-url', help="destination URL")
@click.argument("source")
@click.argument("destination")
@pass_config
def data_copy(config, start, end, source, destination, dest_url):
    src_url = config.url

    if dest_url is None:
        dest_url = src_url

    # determine if the source node is NilmDB or Joule
    try:
        resp = get(src_url)
    except (ConnectionError, requests.exceptions.RequestException) as e:
        raise click.ClickException(str(e))
    if "NilmDB" in resp.text:
        nilmdb_source = True
    elif "Joule" in resp.text:
        nilmdb_source = False
    else:
        raise click.ClickException("invalid source URL: must be a Joule or NilmDB server")

    # determine if the destination node is NilmDB or Joule
    try:
        resp = get(dest_url)
    except (ConnectionError, requests.exceptions.RequestException) as e:
        raise click.ClickException(str(e))
    if "NilmDB" in resp.text:
        nilmdb_dest = True
    elif "Joule" in resp.text:
        nilmdb_dest = False
    else:
        raise click.ClickException("invalid destination URL: must be a Joule or NilmDB server")

    # retrieve the source stream
    src_stream = _retrieve_source(src_url, source, is_nilmdb=nilmdb_source)

    # retrieve the destination stream (create it if necessary)
    dest_stream = _retrieve_destination(dest_url, destination, src_stream, is_nilmdb=nilmdb_dest)
    # make sure streams are compatible
    if src_stream.layout != dest_stream.layout:
        raise click.ClickException("Error: source (%s) and destination (%s) datatypes are not compatible" % (
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
    if element_warning:
        click.confirm("WARNING: Element configurations do not match. Continue?", abort=True)
    # make sure the time bounds make sense
    if start is not None:
        start = int(dateparser.parse(start).timestamp() * 1e6)
    if end is not None:
        end = int(dateparser.parse(end).timestamp() * 1e6)
    if (start is not None) and (end is not None) and ((end - start) <= 0):
        raise click.ClickException("Error: start [%s] must be before end [%s]" % (
            datetime.datetime.fromtimestamp(start / 1e6),
            datetime.datetime.fromtimestamp(end / 1e6)))
    # compute the target intervals (source - dest)
    src_intervals = _get_intervals(src_url, src_stream, source, start, end, is_nilmdb=nilmdb_source)
    dest_intervals = _get_intervals(dest_url, dest_stream, destination, start, end, is_nilmdb=nilmdb_dest)
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
        async with aiohttp.ClientSession() as session:
            if nilmdb_source:
                params = {'path': source, 'binary': 1,
                          'start': istart, 'end': iend}
                url = "{server}/stream/extract".format(server=src_url)
            else:
                params = {'id': src_stream.id, 'start': istart, 'end': iend}
                url = "{server}/data".format(server=src_url)
            async with session.get(url, params=params) as src_response:
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
                    params = {"start": istart, "end": iend, "path": destination, "binary": 1}
                    url = "{server}/stream/insert".format(server=dest_url)
                    await _send_nilmdb_data(url, params, _data_sender(),
                                            pipes.compute_dtype(dest_stream.layout),
                                            session)
                else:
                    async with session.post(dest_url+"/data",
                                            params={"id": dest_stream.id},
                                            data=_data_sender(),
                                            chunked=True) as dest_response:
                        if dest_response.status != 200:
                            msg = await dest_response.text()
                            print("url: ", url)
                            raise click.ClickException("Error writing to destination: %s" % msg)

    # set up aiohttp to handle the response as a JoulePipe
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(_copy(new_intervals))
        click.echo("OK")
    # this should be caught by the stream info requests
    # it is only generated if the joule server stops during the
    # data read/write
    except aiohttp.ClientError as e:  # pragma: no cover
        raise click.ClickException("Error: %s" % str(e))
    loop.close()


def _get_intervals(server: str, my_stream: Stream, path: str,
                   start: Optional[int], end: Optional[int],
                   is_nilmdb: bool = False) -> List[Interval]:
    if is_nilmdb:
        intervals = []
        params = {"path": path}
        url = "{server}/stream/intervals".format(server=server)
        resp = get(url, params=params)
        if not resp.ok:
            raise click.ClickException("unable to retrieve intervals for [%s]" % path)
        if resp.text == '':
            return intervals
        for line in resp.text.strip().split("\n"):
            intervals.append(json.loads(line))
        return intervals

    # otherwise this is a Joule server
    params = {'id': my_stream.id}
    if start is not None:
        params['start'] = start
    if end is not None:
        params['end'] = end

    resp = requests.get(server + "/data/intervals.json", params=params)
    return resp.json()


def _retrieve_source(url: str, path: str, is_nilmdb: bool = False) -> Stream:
    if is_nilmdb:
        src_stream, src_info = _retrieve_nilmdb_stream(url, path)
        if src_stream is None:
            raise click.ClickException("The stream [%s] is not available on [%s]" % (path, url))
    else:
        try:
            resp = get_json(url + "/stream.json", params={"path": path})
        except ConnectionError as e:
            raise click.ClickException(str(e))

        src_stream = stream.from_json(resp)
        src_info: StreamInfo = StreamInfo(**resp['data_info'])
    if src_info.start is None or src_info.end is None:
        raise click.ClickException("[%s] has no data" % path)
    return src_stream


def _retrieve_destination(server: str, path: str, template: Stream, is_nilmdb: bool = False) -> Stream:
    if is_nilmdb:
        dest_stream, dest_info = _retrieve_nilmdb_stream(server, path)
        if dest_stream is None:
            return _create_nilmdb_stream(server, path, template)
        else:
            return dest_stream
    else:
        resp = get(server + "/stream.json", params={"path": path})
        if resp.status_code == 404:
            return _create_joule_stream(server, path, template)
        if not resp.ok:
            raise click.ClickException("Invalid destination: %s" % resp.content.decode())
        try:
            return stream.from_json(resp.json())
        except ValueError:
            raise click.ClickException("Invalid server response, check the URL")


def _create_joule_stream(server: str, path: str, template: Stream) -> Stream:
    click.echo("creating destination stream")
    # split the destination into the path and stream name
    dest_stream = stream.from_json(template.to_json())
    dest_stream.keep_us = Stream.KEEP_ALL
    dest_stream.name = path.split("/")[-1]
    body = {
        "path": "/".join(path.split("/")[:-1]),
        "stream": json.dumps(dest_stream.to_json())
    }
    resp = requests.post(server + "/stream.json", data=body)
    if not resp.ok:
        raise click.ClickException("cannot create [%s] on [%s]" % (path, server))
    return stream.from_json(resp.json())


def _create_nilmdb_stream(server: str, path: str, template: Stream):
    click.echo("creating destination stream")
    dest_stream = stream.from_json(template.to_json())
    dest_stream.keep_us = Stream.KEEP_ALL
    dest_stream.name = path.split("/")[-1]

    url = "{server}/stream/create".format(server=server)
    data = {"path": path,
            "layout": dest_stream.layout}
    resp = requests.post(url, data=data)
    if not resp.ok:
        raise click.ClickException("cannot create [%s] on [%s]" % (path, server))
    # add the metadata
    url = "{server}/stream/set_metadata".format(server=server)
    params = {
        "path": path,
        "data": json.dumps({"config_key__": json.dumps(dest_stream.to_nilmdb_metadata())})
    }
    resp = requests.post(url, params)
    if not resp.ok:
        raise click.ClickException("cannot create metadata for [%s] on [%s]" % (path, server))
    return dest_stream


def _retrieve_nilmdb_stream(server: str, path: str) -> Tuple[Optional[Stream], Optional[StreamInfo]]:
    url = "{server}/stream/get_metadata".format(server=server)
    params = {"path": path, "key": ['config_key__']}
    resp = get(url, params)
    if resp.status_code == 404:
        return None, None
    if not resp.ok:
        raise click.ClickException("[%s]: %s" % (server, resp.text))
    default_name = path.split("/")[-1]
    config_data = {'name': default_name}
    try:
        metadata = resp.json()
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
    resp = get(url, params)
    info = resp.json()[0]
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
                raise click.ClickException("Error writing to destination: %s" % msg)
        bstart = bend
