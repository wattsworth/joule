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

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(
            config.node.event_stream_delete(stream))
        click.echo("OK")

    except errors.ApiError as e:
        raise click.ClickException(str(e))
    finally:
        loop.run_until_complete(
            config.close_node())
        loop.close()

