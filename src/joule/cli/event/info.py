import click
import datetime
import asyncio

from joule import errors
from joule.cli.config import pass_config


@click.command(name="info")
@click.argument("path")
@pass_config
def cli_info(config, path):
    """Display event stream information."""
    try:
        asyncio.run(
            _run(config.node, path))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        asyncio.run(
            config.close_node())


async def _run(node, path):
    my_stream = await node.event_stream_get(path)
    my_info = await node.event_stream_info(my_stream)
    # display stream information
    click.echo()
    click.echo("Event Stream Information:")
    click.echo("\tName:         %s" % my_stream.name)
    click.echo("\tStart:        %s" % _display_time(my_info.start))
    click.echo("\tEnd:          %s" % _display_time(my_info.end))
    click.echo("\tRows:         %d" % my_info.event_count)


def _display_time(time: int) -> str:
    if time is None:
        return u"\u2014"  # emdash
    return str(datetime.datetime.fromtimestamp(time / 1e6))


def _optional_field(value: str) -> str:
    if value is None or value == "":
        return u"\u2014"  # emdash
    else:
        return value
