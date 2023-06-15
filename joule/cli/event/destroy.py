import click
import asyncio

from joule import errors
from joule.cli.config import pass_config


@click.command(name="delete")
@click.argument("stream")
@pass_config
def cli_delete(config, stream):
    """Delete an event stream."""
    if not click.confirm("Delete event stream [%s]?" % stream):
        click.echo("Aborted!")
        return

    try:
        asyncio.run(
            config.node.event_stream_delete(stream))
        click.echo("OK")

    except errors.ApiError as e:
        raise click.ClickException(str(e))
    finally:
        asyncio.run(
            config.close_node())

