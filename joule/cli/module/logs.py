import click
import asyncio

from joule import errors
from joule.api import BaseNode
from joule.cli.config import pass_config


@click.command(name="logs")
@click.argument("name")
@pass_config
def cli_logs(config, name):
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


async def _run(node: BaseNode, name:str):
    logs = await node.module_logs(name)
    for line in logs:
        print(line)
