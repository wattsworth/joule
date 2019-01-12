import click
import asyncio

from joule import errors
from joule.api import node
from joule.cli.config import Config, pass_config
from joule.api.folder import (folder_delete,
                              folder_move)


@click.command(name="move")
@click.argument("source")
@click.argument("destination")
@pass_config
def move(config: Config, source: str, destination: str):
    session = node.Session(config.url)
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(
            folder_move(session, source, destination))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        loop.run_until_complete(
            session.close())
        loop.close()
    click.echo("OK")


@click.command(name="delete")
@click.option("--recursive", "-r", is_flag=True)
@click.argument("folder")
@pass_config
def delete(config, folder, recursive):
    if recursive:
        click.confirm("Delete folder and all subfolders and streams [%s]?" % folder,
                      abort=True)

    session = node.Session(config.url)
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(
            folder_delete(session, folder, recursive))
        click.echo("OK")
    except errors.ApiError as e:
        raise click.ClickException(str(e))
    finally:
        loop.run_until_complete(
            session.close())
        loop.close()


@click.group(name="folder")
def folders():
    """Manage Joule folders"""
    pass  # pragma: no cover


folders.add_command(move)
folders.add_command(delete)