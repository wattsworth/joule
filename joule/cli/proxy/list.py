import click
import asyncio
from tabulate import tabulate

from joule import errors
from joule.api import node
from joule.api.proxy import (proxy_list)
from joule.cli.config import pass_config


@click.command(name="list")
@pass_config
def cli_list(config):
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(
            _run(config.session))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        loop.run_until_complete(
            config.session.close())
        loop.close()


async def _run(session):
    proxies = await proxy_list(session)
    # display module information
    headers = ['Name', 'Target URL', 'Proxy URL']
    result = []
    for proxy in proxies:
        data = [proxy.name, proxy.target_url, proxy.proxied_url]
        result.append(data)
    click.echo(tabulate(result,
                        headers=headers,
                        tablefmt="fancy_grid"))
