import click
import asyncio

from joule import errors
from joule.cli.config import Config, pass_config


@click.command(name="move")
@click.argument("source")
@click.argument("destination")
@pass_config
def cli_move(config: Config, source, destination):
    """Move a data stream to a different folder"""
    try:
        asyncio.run(
            config.node.data_stream_move(source, destination))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        asyncio.run(
            config.close_node())
    click.echo("OK")
