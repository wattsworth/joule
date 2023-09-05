import click
import asyncio

from joule.cli.config import pass_config
from joule import errors


@click.command(name="info")
@pass_config
def node_info(config):
    """Display information about a node."""
    try:
        asyncio.run(
            _run(config.node))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e

    finally:
        asyncio.run(
            config.close_node())
        


# https://stackoverflow.com/questions/1094841
def sizeof_fmt(num, suffix='B'):
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


async def _run(node):
    info = await node.info()
    click.echo("Server Version:   \t%s" % info.version)
    click.echo("Database Location:\t%s" % info.path)
    if info.path != "--remote-database--":
        click.echo("Database Size:    \t%s" % sizeof_fmt(info.size_db))
        click.echo("Space Available:  \t%s" % sizeof_fmt(info.size_free))
