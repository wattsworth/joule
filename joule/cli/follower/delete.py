import click
import asyncio

from joule import errors
from joule.api import BaseNode
from joule.cli.config import pass_config


@click.command(name="delete")
@click.argument("name")
@pass_config
def follower_delete(config, name):
    """Remove a follower"""
    try:
        asyncio.run(config.node.follower_delete(name))
        click.echo("Follower [%s] removed" % name)
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        asyncio.run(
            config.close_node())
