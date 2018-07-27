import click
import requests
from treelib import Tree
from typing import Dict

from joule.cmds.helpers import get_json
from joule.cmds.config import pass_config


@click.command(name="list")
@pass_config
def stream_list(config):
    json = get_json(config.url+"/streams.json")

    json["name"] = ""
    tree = Tree()
    _process_folder(tree, json, None)
    click.echo(tree.show())


def _process_folder(tree: Tree, folder, parent_id):
    tag = folder["name"]
    identifier = "f%d" % folder["id"]
    tree.create_node(tag, identifier, parent_id)
    for stream in folder["streams"]:
        _process_stream(tree, stream, identifier)
    for child in folder["children"]:
        _process_folder(tree, child, identifier)


def _process_stream(tree: Tree, stream, parent_id):
    dtype = "%s_%d" % (stream["datatype"].lower(), len(stream["elements"]))
    tag = "%s: %s" % (stream["name"], dtype)
    identifier = "s%d" % stream["id"]
    tree.create_node(tag, identifier, parent_id)
