import click
import asyncio

from joule.cli.config import pass_config
from joule.api import node
from joule import errors


@click.command(name="info")
@pass_config
def node_info(config):
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(
            _run(config.session))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        loop.run_until_complete(
            config.session.close())
        loop.close()


async def _run(session):
    info = await node.node_info(session)
    click.echo("Server Version: %s" % info.version)
    click.echo("Status: online")
