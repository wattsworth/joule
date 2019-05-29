import click
import asyncio
import signal

from joule.cli.config import pass_config
from joule.models.pipes import EmptyPipe
from joule.api.data import (data_subscribe,
                            data_read)
from joule import errors
from joule.utilities import human_to_timestamp

stop_requested = False


@click.command(name="read")
@click.option('-s', "--start", help="timestamp or descriptive string")
@click.option('-e', "--end", help="timestamp or descriptive string")
@click.option('-l', "--live", is_flag=True, help="subscribe to an active stream")
@click.option('-r', "--max-rows", help="limit response data", type=int)
@click.option('-b', "--show-bounds", is_flag=True, help="include min/max for decimated data")
@click.option('-m', "--mark-intervals", help="include [# interval break] tags", is_flag=True)
@click.argument("stream")
@pass_config
def cmd(config, start, end, live, max_rows, show_bounds, mark_intervals, stream):
    signal.signal(signal.SIGTERM, handler)
    signal.signal(signal.SIGINT, handler)

    if live and (start is not None or end is not None):
        raise click.ClickException("specify either --live or --start/--end, not both")
    if live and max_rows is not None:
        raise click.ClickException("cannot specify --live and --max-rows")
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

    loop = asyncio.get_event_loop()

    async def _run():
        if live:
            pipe = await config.node.data_subscribe(stream)
        else:
            pipe = await config.node.data_read(stream, start, end, max_rows)
        try:
            while not stop_requested:
                try:
                    data = await asyncio.wait_for(pipe.read(flatten=True), 1)
                except asyncio.TimeoutError:
                    # check periodically for Ctrl-C (SIGTERM) even if server is slow
                    continue
                if pipe.decimated and not show_bounds:
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
        await pipe.close()

    try:
        loop.run_until_complete(_run())
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        loop.run_until_complete(
            config.close_node())
        loop.close()


def handler(signum, frame):
    global stop_requested
    stop_requested = True
