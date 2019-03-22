import click
import asyncio

from joule.cli.config import pass_config
from joule.api.session import Session
from joule.api.node import (node_info)
from joule import errors


@click.command(name="info")
@pass_config
def cmd(config):
    session = Session(config.url)
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(_run(session))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        loop.run_until_complete(
            session.close())
        loop.close()


async def _run(session):
    my_info = await node_info(session)
    # display info
    click.echo("Server Version: %s" % my_info.version)
    click.echo("Status: online")
