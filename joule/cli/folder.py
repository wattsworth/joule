import click
import asyncio

from joule import errors
from joule.cli.config import Config, pass_config
from joule.api import BaseNode


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


@click.command(name="rename")
@click.argument("folder")
@click.argument("name")
@pass_config
def rename(config: Config, folder, name):
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(
            _run_rename(config.node, folder, name))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        loop.run_until_complete(
            config.close_node())
        loop.close()
    click.echo("OK")


async def _run_rename(node: BaseNode, folder_path: str, name: str):
    folder = await node.folder_get(folder_path)
    folder.name = name
    await node.folder_update(folder)


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
folders.add_command(rename)
