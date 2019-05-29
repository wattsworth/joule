import click
import asyncio

from joule import errors
from joule.cli.config import pass_config


@click.command(name="delete")
@click.argument("type", type=click.Choice(['user', 'joule', 'lumen']))
@click.argument("name")
@pass_config
def cli_delete(config, type, name):
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(
            _run(config.node, type, name))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        loop.run_until_complete(
            config.close_node())
        loop.close()


async def _run(node, master_type, name):
    await node.master_delete(master_type, name)
    click.echo("Access to node [%s] revoked for %s [%s]" % (node.name, master_type, name))
