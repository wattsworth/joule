import click
import asyncio

from joule import errors
from joule.api import node
from joule.api.proxy import (proxy_get)
from joule.cli.config import Config, pass_config


@click.command(name="info")
@click.argument("name")
@pass_config
def cli_info(config: Config, name: str):
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(
            _run(config.node, name))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        loop.run_until_complete(
            config.close_node())
        loop.close()


async def _run(node: node.BaseNode, name: str):
    proxy = await node.proxy_get(name)
    # display proxy information
    click.echo()
    click.echo("ID:\n\t%d" % proxy.id)
    click.echo("Name:\n\t%s" % proxy.name)
    click.echo("Proxy URL:\n\t%s/interface/p%d/" % (node.url, proxy.id))
    click.echo("Source URL:\n\t%s" % proxy.url)



