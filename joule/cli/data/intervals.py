import click
import asyncio

from joule import errors
from joule.api.session import Session
from joule.api.data import data_intervals
from joule.cli.config import Config, pass_config
from joule.utilities import timestamp_to_human, human_to_timestamp


@click.command(name="intervals")
@click.option('-s', "--start", help="timestamp or descriptive string")
@click.option('-e', "--end", help="timestamp or descriptive string")
@click.argument("stream")
@pass_config
def intervals(config: Config, start, end, stream: str):
    if start is not None:
        try:
            start = human_to_timestamp(start)
        except ValueError:
            raise click.ClickException("invalid start time: [%s]" % start)
    if end is not None:
        try:
            end = human_to_timestamp(end)
        except ValueError:
            raise click.ClickException("invalid end time: [%s]" % end)


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
