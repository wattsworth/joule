import click
import asyncio
from treelib import Tree

from joule import errors
from joule.api.session import Session
from joule.api.stream import Stream
from joule.api.folder import (Folder, folder_root)
from joule.cli.config import pass_config


@click.command(name="list")
@click.option("--layout", "-l", is_flag=True, help="include stream layout")
@click.option("--status", "-s", is_flag=True, help="include stream status")
@pass_config
def cli_list(config, layout, status):
    session = Session(config.url)
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(
            _run(session, layout, status))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        loop.run_until_complete(
            session.close())
        loop.close()


async def _run(session, layout: bool, status: bool):
    tree = Tree()
    root = await folder_root(session)
    root.name = ""  # omit root name
    _process_folder(tree, root, None, layout, status)
    if status:
        click.echo("Legend: " + click.style("\u25CF ", fg="green") + "active  " +
                   click.style("\u25CF ", fg="cyan") + "configured")
    click.echo(tree.show())


def _process_folder(tree: Tree, folder: Folder, parent_id, layout: bool, status: bool):
    tag = click.style(folder.name, bold=True)
    identifier = "f%d" % folder.id
    tree.create_node(tag, identifier, parent_id)
    for stream in folder.streams:
        _process_stream(tree, stream, identifier, layout, status)
    for child in folder.children:
        _process_folder(tree, child, identifier, layout, status)


def _process_stream(tree: Tree, stream: Stream, parent_id, layout: bool, status: bool):
    tag = stream.name + "(%d)" % stream.id
    if layout:
        tag += stream.layout
    if status:
        if stream.active:
            tag = click.style("\u25CF ", fg="green") + tag
        elif stream.locked:
            tag = click.style("\u25CF ", fg="cyan") + tag
        else:
            tag = "  " + tag
    identifier = "s%d" % stream.id
    tree.create_node(tag, identifier, parent_id)
