import click
import asyncio
import datetime

from joule import errors
from joule.api import BaseNode
from joule.cli.config import Config, pass_config


@click.command(name="info")
@click.argument("name")
@pass_config
def cli_info(config: Config, name: str):
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


async def _run(node: BaseNode, name: str):
    module = await node.module_get(name)
    # display module information
    click.echo()
    if module.is_app:
        click.echo("This is module is a Data App\n")
    click.echo("Name:\n\t%s" % module.name)
    if len(module.description) > 0:
        click.echo("Description:\n\t%s" % module.description)
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
    click.echo("CPU Usage:\n\t%0.2f%%" % module.statistics.cpu_percent)
    click.echo("Memory Usage:\n\t%0.2f%%" % module.statistics.memory_percent)
    now = datetime.datetime.now().timestamp()
    delta = datetime.timedelta(seconds=now - module.statistics.create_time)

    click.echo("Uptime:\n\t%s" % delta)
    click.echo("")


