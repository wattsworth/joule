import click
import asyncio
from treelib import Tree

from joule import errors
from joule.api.stream import Stream
from joule.api.folder import (Folder, folder_root)
from joule.cli.config import pass_config
from joule.api import BaseNode

@click.command(name="list")
@click.option("--layout", "-l", is_flag=True, help="include stream layout")
@click.option("--status", "-s", is_flag=True, help="include stream status")
@click.option("--id", "-i", is_flag=True, help="show ID's")
@pass_config
def cli_list(config, layout, status, id):
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(
            _run(config.node, layout, status, id))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        loop.run_until_complete(
            config.close_node())
        loop.close()


async def _run(node: BaseNode, layout: bool, status: bool, showid: bool):
    tree = Tree()
    root = await node.folder_root()
    root.name = ""  # omit root name
    _process_folder(tree, root, None, layout, status, showid)
    if status:
        click.echo("Legend: " + click.style("\u25CF ", fg="green") + "active  " +
                   click.style("\u25CF ", fg="cyan") + "configured")
    click.echo(tree.show())


def _process_folder(tree: Tree, folder: Folder, parent_id,
                    layout: bool, status: bool, showid: bool):
    tag = click.style(folder.name, bold=True)
    if showid:
        tag += " (%d)" % folder.id
    identifier = "f%d" % folder.id
    tree.create_node(tag, identifier, parent_id)
    for stream in folder.streams:
        _process_stream(tree, stream, identifier, layout, status, showid)
    for child in folder.children:
        _process_folder(tree, child, identifier, layout, status, showid)


def _process_stream(tree: Tree, stream: Stream, parent_id,
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
