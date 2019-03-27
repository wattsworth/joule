import click
import asyncio
from tabulate import tabulate

from joule.api.master import master_list
from joule.cli.config import pass_config
from joule import errors


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
    masters = await master_list(session)
    # display module information
    users = [m.name for m in masters if m.master_type == 'USER']
    nodes = [m.name for m in masters if m.master_type == 'NODE']
    click.echo("Users:")
    if len(users) > 0:
        for user in users:
            click.echo("\t%s"%user)
    else:
        click.echo("\tNo users can control this node")
    click.echo("Nodes:")
    if len(nodes) > 0:
        click.echo(tabulate(nodes,
                            headers=["Name"],
                            tablefmt="fancy_grid"))
    else:
        click.echo("\tNo other nodes can control this node")
