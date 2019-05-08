import click
import asyncio

from joule import errors
from joule.cli.config import pass_config
from joule.api import BaseNode

@click.command(name="add")
@click.argument("type", type=click.Choice(['user','node']))
@click.argument("identifier")
@pass_config
def cli_add(config, type, identifier):
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(
            _run(config.node, type, identifier))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        loop.run_until_complete(
            config.node.close())
        loop.close()


async def _run(node: BaseNode, type, identifier):
    result = await node.master_add(type, identifier)
    if type == "user":
        click.echo("Access to node [%s] granted to user [%s]" % (node.name, identifier))
        click.echo("")
        click.echo("Key:\t%s" % result.key)
        click.echo("")
        click.echo("Run [joule node add] with the above values on the user's machine")
        click.echo("* IP address may differ based on network setup")
    else:
        click.echo("Access to node [%s] granted to node [%s]" % (node.name, result.name))
