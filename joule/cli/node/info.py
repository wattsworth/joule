import click
import asyncio

from joule.cli.config import pass_config
from joule import errors


@click.command(name="info")
@pass_config
def node_info(config):
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(
            _run(config.node))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e

    finally:
        loop.run_until_complete(
            config.close_node())
        loop.close()


async def _run(node):
    info = await node.info()
    click.echo("Server Version: %s" % info.version)
    click.echo("Status: online")
