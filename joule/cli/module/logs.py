import click
import asyncio

from joule import errors
from joule.api import BaseNode
from joule.cli.config import pass_config


@click.command(name="logs")
@click.argument("name")
@pass_config
def cli_logs(config, name):
    """Display a module's log output"""
    try:
        asyncio.run(
            _run(config.node, name))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        asyncio.run(
            config.close_node())


async def _run(node: BaseNode, name:str):
    logs = await node.module_logs(name)
    for line in logs:
        print(line)
