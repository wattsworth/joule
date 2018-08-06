import click
import requests
from treelib import Tree
from typing import Dict

from joule.cmds.helpers import get_json
from joule.cmds.config import pass_config


@click.command(name="list")
@click.option("--layout", "-l", is_flag=True, help="include stream layout")
@click.option("--status", "-s", is_flag=True, help="include stream status")
@pass_config
def stream_list(config, layout, status):
    json = get_json(config.url + "/streams.json")

    json["name"] = ""
    tree = Tree()
    _process_folder(tree, json, None, layout, status)
    if status:
        click.echo("Legend: " + click.style("\u25CF ", fg="green") + "active  " +
                   click.style("\u25CF ", fg="black") + "configured")
    click.echo(tree.show())


def _process_folder(tree: Tree, folder, parent_id, layout: bool, status: bool):
    tag = click.style(folder["name"], bold=True)
    identifier = "f%d" % folder["id"]
    tree.create_node(tag, identifier, parent_id)
    for stream in folder["streams"]:
        _process_stream(tree, stream, identifier, layout, status)
    for child in folder["children"]:
        _process_folder(tree, child, identifier, layout, status)


def _process_stream(tree: Tree, stream, parent_id, layout: bool, status: bool):
    tag = stream["name"] + "(%d)" % stream["id"]
    if layout:
        tag += ": %s_%d" % (stream["datatype"].lower(), len(stream["elements"]))
    if status:
        if stream["active"]:
            tag = click.style("\u25CF ", fg="green") + tag
        elif stream["locked"]:
            tag = click.style("\u25CF ", fg="black") + tag
        else:
            tag = "  " + tag
    identifier = "s%d" % stream["id"]
    tree.create_node(tag, identifier, parent_id)
