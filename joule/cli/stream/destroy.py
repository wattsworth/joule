import click
import asyncio

from joule import errors
from joule.api import node
from joule.api.stream import stream_delete
from joule.cli.config import pass_config


@click.command(name="delete")
@click.argument("stream")
@pass_config
def cli_delete(config, stream):
    if not click.confirm("Delete stream [%s]?" % stream):
        click.echo("Aborted!")
        return

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(
            stream_delete(config.session, stream))
        click.echo("OK")

    except errors.ApiError as e:
        raise click.ClickException(str(e))
    finally:
        loop.run_until_complete(
            config.session.close())
        loop.close()

