import click
import dateparser
import aiohttp
import asyncio

from joule.cmds.config import pass_config
from joule.models.pipes import InputPipe, EmptyPipe


@click.command(name="read")
@click.option('-s', "--start", help="timestamp or descriptive string")
@click.option('-e', "--end", help="timestamp or descriptive string")
@click.option('-r', "--max-rows", help="limit response data", type=int)
@click.option('-d', "--decimation-level", help="specify a particular decimation", type=int)
@click.option('-b', "--show-bounds", is_flag=True, help="include min/max for decimated data")
@click.option('-m', "--mark-intervals", help="include [# interval break] tags", is_flag=True)
@click.argument("stream")
@pass_config
def data_read(config, start, end, max_rows, decimation_level, show_bounds, mark_intervals, stream):
    params = {"path": stream}
    if start is not None:
        time = dateparser.parse(start)
        if time is None:
            click.echo("Error: invalid start time: [%s]" % start)
            exit(1)
        params['start'] = int(time.timestamp() * 1e6)
    if end is not None:
        time = dateparser.parse(end)
        if time is None:
            click.echo("Error: invalid end time: [%s]" % end)
            exit(1)
        params['end'] = int(time.timestamp() * 1e6)
    if max_rows is not None:
        params['max-rows'] = max_rows
    if decimation_level is not None:
        params['decimation-level'] = decimation_level

    async def _get_data():
        async with aiohttp.ClientSession() as session:
            async with session.get(config.url + "/data", params=params) as response:
                if response.status != 200:
                    click.echo("Error %s [%d]: %s" % (config.url, response.status,
                                                      await response.text()))
                    exit(1)
                decimated = False
                if int(response.headers['joule-decimation']) > 1:
                    decimated = True
                pipe = InputPipe(layout=response.headers['joule-layout'],
                                 reader=response.content)
                try:
                    while True:
                        data = await pipe.read(flatten=True)
                        if decimated and not show_bounds:
                            # suppress the bound information
                            ncols = (data.shape[1] - 1) // 3 + 1
                            data = data[:, :ncols]
                        pipe.consume(len(data))
                        for row in data:
                            line = "%d %s" % (row[0], ' '.join('%f' % x for x in row[1:]))
                            click.echo(line)
                        if pipe.end_of_interval and mark_intervals:
                            click.echo("# interval break")
                except EmptyPipe:
                    pass

    # set up aiohttp to handle the response as a JoulePipe
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(_get_data())
    except aiohttp.ClientError as e:
        print("Error: ", e)
