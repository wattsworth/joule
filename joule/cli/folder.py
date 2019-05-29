import click
import asyncio

from joule import errors
from joule.cli.config import Config, pass_config


@click.command(name="move")
@click.argument("source")
@click.argument("destination")
@pass_config
def move(config: Config, source: str, destination: str):
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(
            config.node.folder_move(source, destination))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        loop.run_until_complete(
            config.close_node())
        loop.close()
    click.echo("OK")


@click.command(name="delete")
@click.option("--recursive", "-r", is_flag=True)
@click.argument("folder")
@pass_config
def delete(config, folder, recursive):
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(
            config.node.folder_delete(folder, recursive))
        click.echo("OK")
    except errors.ApiError as e:
        raise click.ClickException(str(e))
    finally:
        loop.run_until_complete(
            config.close_node())
        loop.close()


@click.group(name="folder")
def folders():
    """Manage Joule folders"""
    pass  # pragma: no cover


folders.add_command(move)
folders.add_command(delete)
