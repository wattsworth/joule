import click
import asyncio

from joule import errors
from joule.cli.config import pass_config
from joule.api.master import master_delete

@click.command(name="delete")
@click.argument("type", type=click.Choice(['user','node']))
@click.argument("name")
@pass_config
def cli_delete(config, type, name):
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(
            _run(config, type, name))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        loop.run_until_complete(
            config.session.close())
        loop.close()


async def _run(config, master_type, name):
    await master_delete(config.session, master_type, name)
    click.echo("Access to node [%s] revoked for user [%s]" % (config.name, name))
