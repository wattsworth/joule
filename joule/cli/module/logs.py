import click
import asyncio

from joule import errors
from joule.api import node
from joule.api.module import (module_logs)
from joule.cli.config import pass_config


@click.command(name="logs")
@click.argument("name")
@pass_config
def cli_logs(config, name):
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


async def _run(session: node.Session, name:str):
    logs = await module_logs(session, name)
    for line in logs:
        print(line)
