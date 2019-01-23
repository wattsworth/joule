import click
import asyncio
import dateparser

from joule import errors
from joule.api.session import Session
from joule.api.data import data_intervals
from joule.cli.config import Config, pass_config
from joule.utilities import timestamp_to_human


@click.command(name="intervals")
@click.option('-s', "--start", help="timestamp or descriptive string")
@click.option('-e', "--end", help="timestamp or descriptive string")
@click.argument("stream")
@pass_config
def intervals(config: Config, start, end, stream: str):
    if start is not None:
        time = dateparser.parse(start)
        if time is None:
            raise click.ClickException("Error: invalid start time: [%s]" % start)
        start = int(time.timestamp() * 1e6)
    if end is not None:
        time = dateparser.parse(end)
        if time is None:
            raise click.ClickException("Error: invalid end time: [%s]" % end)
        end = int(time.timestamp() * 1e6)

    session = Session(config.url)
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(_run(session, start, end, stream))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        loop.run_until_complete(
            session.close())
        loop.close()


async def _run(session, start, end, stream):
    my_intervals = await data_intervals(session, stream, start, end)
    if len(my_intervals) == 0:
        print("no stream data")
        return
    for interval in my_intervals:
        print("[%s - %s]" % (
            timestamp_to_human(interval[0]),
            timestamp_to_human(interval[1])))
