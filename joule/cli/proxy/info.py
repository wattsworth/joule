import click
import asyncio
import datetime

from joule import errors
from joule.api import node
from joule.api.proxy import (proxy_get)
from joule.cli.config import Config, pass_config


@click.command(name="info")
@click.argument("name")
@pass_config
def cli_info(config: Config, name: str):
    session = node.Session(config.url)
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(
            _run(session, name))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        loop.run_until_complete(
            session.close())
        loop.close()


async def _run(session: node.Session, name: str):
    proxy = await proxy_get(session, name)
    # display proxy information
    click.echo()
    click.echo("ID:\n\t%d" % proxy.id)
    click.echo("Name:\n\t%s" % proxy.name)
    click.echo("Proxy URL:\n\t%s/interface/p%d/" % (session.url, proxy.id))
    click.echo("Source URL:\n\t%s" % proxy.url)



