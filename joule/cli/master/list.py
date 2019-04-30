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
            config.node.close())
        loop.close()


async def _run(node):
    click.echo("This node can be controlled by:")
    masters = await node.master_list()
    # display module information
    users = [m.name for m in masters if m.master_type == 'USER']
    nodes = [m.name for m in masters if m.master_type == 'NODE']
    click.echo("Users:")
    if len(users) > 0:
        for user in users:
            click.echo("\t%s" % user)
    else:
        click.echo("\t[None]")
    click.echo("Nodes:")
    if len(nodes) > 0:
        for node in nodes:
            click.echo("\t%s" % node)
    else:
        click.echo("\t[None]")
