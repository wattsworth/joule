import click
import asyncio

from joule.cli.config import pass_config
from joule import errors


@click.command(name="list")
@pass_config
def cli_list(config):
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
    click.echo("This node can be controlled by:")
    masters = await node.master_list()
    # display module information
    users = [m.name for m in masters if m.master_type == 'USER']
    joule_nodes = [m.name for m in masters if m.master_type == 'JOULE_NODE']
    lumen_nodes = [m.name for m in masters if m.master_type == 'LUMEN_NODE']
    click.echo("Users:")
    if len(users) > 0:
        for user in users:
            click.echo("\t%s" % user)
    else:
        click.echo("\t[None]")
    click.echo("Joule Nodes:")
    if len(joule_nodes) > 0:
        for node in joule_nodes:
            click.echo("\t%s" % node)
    else:
        click.echo("\t[None]")
    click.echo("Lumen Nodes:")
    if len(lumen_nodes) > 0:
        for node in lumen_nodes:
            click.echo("\t%s" % node)
    else:
        click.echo("\t[None]")
