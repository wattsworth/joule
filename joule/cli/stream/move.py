import click
import asyncio

from joule import errors
from joule.api import node
from joule.api.stream import stream_move
from joule.cli.config import Config, pass_config


@click.command(name="move")
@click.argument("source")
@click.argument("destination")
@pass_config
def cli_move(config: Config, source, destination):
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(
            stream_move(config.session, source, destination))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        loop.run_until_complete(
            config.session.close())
        loop.close()
    click.echo("OK")
