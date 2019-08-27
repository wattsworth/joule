import click
import asyncio
from tabulate import tabulate

from joule import errors
from joule.api import BaseNode
from joule.cli.config import pass_config


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


async def _run(node: BaseNode):
    proxies = await node.proxy_list()
    # display module information
    headers = ['ID', 'Name', 'Target URL']
    result = []
    for proxy in proxies:
        data = [proxy.id, proxy.name, proxy.target_url]
        result.append(data)
    click.echo(tabulate(result,
                        headers=headers,
                        tablefmt="fancy_grid"))
