import click
import requests
from operator import attrgetter
import dateparser
import aiohttp
import asyncio
import json
import datetime

from joule.cmds.config import pass_config
from joule.cmds.helpers import get_json, get
from joule.models import stream, Stream, pipes, StreamInfo


@click.command(name="copy")
@click.option("--start", help="timestamp or descriptive string")
@click.option("--end", help="timestamp or descriptive string")
@click.argument("source")
@click.argument("destination")
@pass_config
def data_copy(config, start, end, source, destination):
    # retrieve the source stream
    resp = get_json(config.url + "/stream.json", params={"path": source})
    src_stream = stream.from_json(resp['stream'])
    src_info: StreamInfo = StreamInfo(**resp['data_info'])
    if src_info.start is None or src_info.end is None:
        click.echo("Error [%s] has no data" % source, err=True)
        exit(1)
    # retrieve the destination stream (create it if necessary)
    resp = get(config.url + "/stream.json", params={"path": destination})
    if resp.status_code == 404:
        click.echo("creating destination stream")
        # split the destination into the path and stream name
        dest_stream = stream.from_json(src_stream.to_json())
        dest_stream.keep_us = Stream.KEEP_ALL
        dest_stream.name = destination.split("/")[-1]
        body = {
            "path": "/".join(destination.split("/")[:-1]),
            "stream": json.dumps(dest_stream.to_json())
        }
        resp = requests.post(config.url + "/stream.json", data=body)
        if resp.status_code != 200:
            click.echo("Error: invalid destination: %s" % resp.content.decode(), err=True)
            exit(1)
        else:
            dest_stream = stream.from_json(resp.json())
    else:
        dest_stream = None  # to appease type checker
        try:
            dest_stream = stream.from_json(resp.json()['stream'])
        except ValueError:
            click.echo("Error: Invalid server response, check the URL")
            exit(1)

    # make sure streams are compatible
    if src_stream.layout != dest_stream.layout:
        click.echo("Error: source (%s) and destination (%s) datatypes are not compatible" % (
            src_stream.layout, dest_stream.layout))
        exit(1)
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
    params = {"path": source}
    if start is None:
        start = src_info.start
    else:
        start = int(dateparser.parse(start).timestamp() * 1e6)

    if end is None:
        end = src_info.end
    else:
        end = int(dateparser.parse(end).timestamp() * 1e6)
    duration = end - start
    if duration <= 0:
        click.echo("Error: start [%s] must be before end [%s]" % (
            datetime.datetime.fromtimestamp(start / 1e6),
            datetime.datetime.fromtimestamp(end / 1e6)))
        exit(1)

    async def _copy_data():
        async with aiohttp.ClientSession() as session:
            async with session.get(config.url + "/data", params=params) as src_response:
                if src_response.status != 200:
                    msg = await src_response.text()
                    click.echo("Error reading from source: %s" % msg)
                    exit(1)

                pipe = pipes.InputPipe(stream=dest_stream, reader=src_response.content)

                async def _data_sender():
                    with click.progressbar(
                            label='Copying data',
                            length=duration) as bar:
                        last_ts = start
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
                                if pipe.end_of_interval:
                                    yield pipes.interval_token(dest_stream.layout). \
                                        tostring()
                        except pipes.EmptyPipe:
                            pass
                        bar.update(end - last_ts)

                async with session.post(config.url + "/data",
                                        params={"id": dest_stream.id},
                                        data=_data_sender()) as dest_response:
                    if dest_response.status != 200:
                        msg = await dest_response.text()
                        click.echo("Error writing to destination: %s" % msg)
                        exit(1)
    # set up aiohttp to handle the response as a JoulePipe
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(_copy_data())
        click.echo("OK")
    # this should be caught by the stream info requests
    # it is only generated if the joule server stops during the
    # data read/write
    except aiohttp.ClientError as e:  # pragma: no cover
        click.echo("Error: ", e)
        exit(1)
    loop.close()
