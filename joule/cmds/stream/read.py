import click
import dateparser
import aiohttp
import asyncio
import requests
import pdb

from joule.cmds.config import pass_config
from joule.models.stream import from_json
from joule.models.pipes import InputPipe, EmptyPipe


@click.command(name="read-data")
@click.option("--start")
@click.option("--end")
@click.option("--max-rows", type=int)
@click.option("--decimation-level", type=int)
@click.option("--mark-intervals", default=False)
@click.argument("stream")
@pass_config
def read_data(config, start, end, max_rows, decimation_level, mark_intervals, stream):
    params = {"path": stream}
    if start is not None:
        params['start'] = int(dateparser.parse(start).timestamp() * 1e6)
    if end is not None:
        params['end'] = int(dateparser.parse(end).timestamp() * 1e6)
    if max_rows is not None:
        params['max-rows'] = max_rows
    if decimation_level is not None:
        params['decimation-level'] = decimation_level

    # get the stream object so we can decode the data
    resp = requests.get(config.url + "/stream.json", params={"path": stream})
    my_stream = from_json(resp.json()["stream"])

    async def _get_data():
        async with aiohttp.ClientSession() as session:
            async with session.get(config.url + "/data", params=params) as response:
                pipe = InputPipe(stream=my_stream, reader=response.content)
                try:
                    while True:
                        data = await pipe.read()
                        pipe.consume(len(data))
                        for row in data:
                            click.echo('%d ' % row['timestamp'], nl=False)
                            click.echo(' '.join('%f' % x for x in row['data']))
                except EmptyPipe:
                    pass

    # set up aiohttp to handle the response as a JoulePipe
    loop = asyncio.get_event_loop()
    loop.run_until_complete(_get_data())
