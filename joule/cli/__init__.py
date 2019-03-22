import click

from joule.cli.stream import streams
from joule.cli.data import data
from joule.cli.module import module
from joule.cli.folder import folders
from joule.cli.proxy import proxies
from joule.cli.root import info, initialize, authorize
from joule.cli.config import Config, pass_config
from joule.api.session import Session

from .node_utilties import (lookup_node, list_nodes)

@click.group()
@click.option('-n', '--node', default="", help="Joule Node name")
@click.version_option()
@pass_config
def main(config, node_name):
    # create a Node structure for the name
    # if node_name is given use it, otherwise go with the default
    try:
        (url, key) = lookup_node(node_name)
        config.session = Session(url, key)
    except ValueError:
        if len(node_name) > 0:
            print("Invalid node [%s]" % node_name)
        print(list_nodes())
        raise click.ClickException("")


main.add_command(info.cmd)
main.add_command(initialize.cmd)
main.add_command(authorize.cmd)
main.add_command(streams)
main.add_command(data)
main.add_command(module)
main.add_command(folders)
main.add_command(proxies)