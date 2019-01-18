import click
import dateparser
import asyncio

from joule.cli.config import pass_config
from joule.models.pipes import EmptyPipe
from joule.api.node import Node
from joule import errors


@click.command(name="read")
@click.option('-s', "--start", help="timestamp or descriptive string")
@click.option('-e', "--end", help="timestamp or descriptive string")
@click.option('-r', "--max-rows", help="limit response data", type=int)
@click.option('-b', "--show-bounds", is_flag=True, help="include min/max for decimated data")
@click.option('-m', "--mark-intervals", help="include [# interval break] tags", is_flag=True)
@click.argument("stream")
@pass_config
def data_read(config, start, end, max_rows, show_bounds, mark_intervals, stream):

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

    loop = asyncio.get_event_loop()
    my_node = Node(config.url, loop)

    async def _run():
        pipe = await my_node.data_read(stream, start, end, max_rows)
        try:
            while True:
                data = await pipe.read(flatten=True)
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

    try:
        loop.run_until_complete(_run())
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        loop.run_until_complete(
            my_node.close())
        loop.close()
