import click
import asyncio
from treelib import Tree

from joule import errors
from joule.cli.config import Config, pass_config
from joule.api import BaseNode
from joule.api.folder import (Folder, folder_root)
from joule.api.data_stream import DataStream


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


@click.command(name="list")
@click.argument("path", default="/")
@click.option("--layout", "-l", is_flag=True, help="include stream layout")
@click.option("--status", "-s", is_flag=True, help="include stream status")
@click.option("--id", "-i", is_flag=True, help="show ID's")
@pass_config
def list(config, path, layout, status, id):
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(
            _run(config.node, path, layout, status, id))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        loop.run_until_complete(
            config.close_node())
        loop.close()


async def _run(node: BaseNode, path: str, layout: bool, status: bool, showid: bool):
    tree = Tree()
    if path == "/":
        root = await node.folder_root()
        root.name = ""  # omit root name
    else:
        root = await node.folder_get(path)
    _process_folder(tree, root, None, layout, status, showid)
    click.echo("Legend: [" + click.style("Folder", bold=True) + "] [Data Stream] ["
               + click.style("Event Stream", fg='cyan')+"]")
    if status:
        click.echo("\t" + click.style("\u25CF ", fg="green") + "active  " +
                   click.style("\u25CF ", fg="cyan") + "configured")
    click.echo(tree.show())


def _process_folder(tree: Tree, folder: Folder, parent_id,
                    layout: bool, status: bool, showid: bool):
    tag = click.style(folder.name, bold=True)
    if showid:
        tag += " (%d)" % folder.id
    identifier = "f%d" % folder.id
    tree.create_node(tag, identifier, parent_id)
    for stream in folder.data_streams:
        _process_data_stream(tree, stream, identifier, layout, status, showid)
    for stream in folder.event_streams:
        _process_event_stream(tree, stream, identifier, showid)
    for child in folder.children:
        _process_folder(tree, child, identifier, layout, status, showid)


def _process_data_stream(tree: Tree, stream: DataStream, parent_id,
                         layout: bool, status: bool, showid: bool):
    tag = stream.name
    if showid:
        tag += " (%d)" % stream.id
    if layout:
        tag += " (%s)" % stream.layout
    if status:
        if stream.active:
            tag = click.style("\u25CF ", fg="green") + tag
        elif stream.locked:
            tag = click.style("\u25CF ", fg="cyan") + tag

    identifier = "s%d" % stream.id
    tree.create_node(tag, identifier, parent_id)


def _process_event_stream(tree: Tree, stream: DataStream, parent_id, showid: bool):
    tag = stream.name
    if showid:
        tag += " (%d)" % stream.id
    tag = click.style(tag, fg="cyan")
    identifier = "e%d" % stream.id
    tree.create_node(tag, identifier, parent_id)


@click.group(name="folder")
def folders():
    """Manage Joule folders"""
    pass  # pragma: no cover


folders.add_command(move)
folders.add_command(delete)
folders.add_command(rename)
folders.add_command(list)
