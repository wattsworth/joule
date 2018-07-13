import click
import requests
from treelib import Tree
from typing import Dict

from joule.cmds.config import pass_config


@click.command(name="list")
@pass_config
def stream_list(config):
    json = _get(config.url+"/streams.json")

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


def _get(url: str, params=None) -> Dict:
    resp = None  # to appease type checker
    try:
        resp = requests.get(url, params=params)
    except requests.ConnectionError:
        click.echo("Error contacting Joule server at [%s]" % url)
        exit(1)
    if resp.status_code != 200:
        click.echo("Error [%d]: %s" % (resp.status_code, resp.text))
        exit(1)
    try:
        data = resp.json()
        return data
    except ValueError:
        click.echo("Error: Invalid server response, check the URL")
        exit(1)
