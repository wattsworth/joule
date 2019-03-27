import click
import asyncio

from joule import errors
from joule.api.master import master_add
from joule.cli.config import pass_config


@click.command(name="add")
@click.argument("type")
@click.argument("identifier")
@pass_config
def cli_add(config, type, identifier):
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(
            _run(config.session, type, identifier, id))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        loop.run_until_complete(
            config.session.close())
        loop.close()


async def _run(session, type, identifier):
    result = await master_add(session, type, identifier)
    if type == "user":
        click.echo("Access to node [%s] granted to user [%s]" % (session.name, identifier))
        click.echo("Key:\t%s" % result.key)
        click.echo("URL:\t%s (note: IP address may differ based on network setup)" % result.url)
        click.echo("Run [joule node add] with the above values on the user's machine")
    else:
        click.echo("Access to node [%s] granted to node [%s]" % (session.name, result))
