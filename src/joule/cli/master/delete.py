import click
import asyncio

from joule import errors
from joule.cli.config import pass_config


@click.command(name="delete")
@click.argument("type", type=click.Choice(['user', 'joule', 'lumen']))
@click.argument("name")
@pass_config
def cli_delete(config, type, name):
    """
    Revoke access for a user or Joule/Lumen node.

    Specify the type of master and the name as displayed by the 'master list' command
    """
    try:
        asyncio.run(
            _run(config.node, type, name))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        asyncio.run(
            config.close_node())
        


async def _run(node, master_type, name):
    await node.master_delete(master_type, name)
    click.echo("Access to node [%s] revoked for %s [%s]" % (node.name, master_type, name))
