import click
import asyncio

from joule.api.follower import follower_list
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
    followers = await follower_list(session)
    # display follower information
    if len(followers) > 0:
        click.echo("This node can control:")
        for follower in followers:
            click.echo("\t%s" % follower.name)
    else:
        click.echo("This node cannot control any other nodes")
