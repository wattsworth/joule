import click
import requests
from operator import attrgetter
import dateparser
import aiohttp
import asyncio
import json

from joule.cmds.config import pass_config
from joule.models import stream, Stream


@click.command(name="copy-data")
@click.option("--start", help="timestamp or descriptive string")
@click.option("--end", help="timestamp or descriptive string")
@click.argument("source")
@click.argument("destination")
@pass_config
def copy_data(config, start, end, source, destination):
    # retrieve the source stream
    resp = requests.get(config.url + "/stream.json", params={"path": source})
    if resp.status_code != 200:
        click.echo("source error: %s" % resp.content.decode(), err=True)
        return
    src_stream = stream.from_json(resp.json()['stream'])

    # retrieve the destination stream (create it if necessary)
    resp = requests.get(config.url + "/stream.json", params={"path": destination})
    if resp.status_code == 404:
        click.echo("creating destination stream")
        # split the destination into the path and stream name
        dest_stream = stream.from_json(src_stream.to_json())
        dest_stream.keep_us = Stream.KEEP_ALL
        dest_stream.name = destination.split("/")[-1]
        data = {
            "path": "/".join(destination.split("/")[:-1]),
            "stream": json.dumps(dest_stream.to_json())
        }
        resp = requests.post(config.url + "/stream.json", data=data)
        if resp.status_code != 200:
            click.echo("destination error: %s" % resp.content.decode(), err=True)
            return
        else:
            dest_stream = stream.from_json(resp.json())
    else:
        dest_stream = stream.from_json(resp.json()['stream'])

    # make sure streams are compatible
    if src_stream.layout != dest_stream.layout:
        click.echo("ERROR: source (%s) and destination (%s) datatypes are not compatible" % (
            src_stream.layout, dest_stream.layout))
        return

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
        click.echo("WARNING: Element configurations do not match. Continue? (y/n)")

    # make sure the time bounds make sense
    params = {"path": source}
    if start is not None:
        params['start'] = int(dateparser.parse(start).timestamp() * 1e6)
    if end is not None:
        params['end'] = int(dateparser.parse(end).timestamp() * 1e6)

    async def _copy_data():
        async with aiohttp.ClientSession() as session:
            async with session.get(config.url + "/data", params=params) as src_response:
                if src_response.status != 200:
                    msg = await src_response.text()
                    click.echo("Error reading from source: %s" % msg)
                    return
                print("starting the writer!")
                async with session.post(config.url + "/data", data=src_response.content) as dest_response:
                    if dest_response.status != 200:
                        msg = await dest_response.text()
                        click.echo("Error writing to destination: %s" % msg)

    # set up aiohttp to handle the response as a JoulePipe
    loop = asyncio.get_event_loop()
    loop.run_until_complete(_copy_data())
    click.echo("OK")
