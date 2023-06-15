import click
import asyncio

from joule.cli.config import pass_config
from joule import errors


@click.command(name="list")
@pass_config
def cli_list(config):
    """Display node followers"""
    try:
        asyncio.run(
            _run(config.node))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        asyncio.run(
            config.close_node())


async def _run(node):
    followers = await node.follower_list()
    # display follower information
    if len(followers) > 0:
        click.echo("This node can control:")
        for follower in followers:
            click.echo("\t%s" % follower.name)
    else:
        click.echo("This node cannot control any other nodes")
