import click
import asyncio

from joule import errors
from joule.api import node
from joule.api.module import (module_get)
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
    module = await module_get(session, name)
    # display module information
    click.echo()
    click.echo("Name:\n\t%s" % module.name)
    click.echo("Description:\n\t%s" % module.description)
    if module.has_interface:
        click.echo("Interface URL:\n\t%s/interface/%d/" % (session.url, module.id))
    click.echo("Inputs:")
    if len(module.inputs) == 0:
        click.echo("\t--none--")
    else:
        for (name, loc) in module.inputs.items():
            click.echo("\t%s: %s" % (name, loc))
    click.echo("Outputs:")
    if len(module.outputs) == 0:
        click.echo("\t--none--")
    else:
        for (name, loc) in module.outputs.items():
            click.echo("\t%s:\t%s" % (name, loc))


