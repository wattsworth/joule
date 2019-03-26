import click

from joule.cli.stream import streams
from joule.cli.data import data
from joule.cli.module import module
from joule.cli.folder import folders
from joule.cli.proxy import proxies
from joule.cli.root import info
from joule.cli.admin import admin
from joule.cli.config import Config, pass_config



@click.group()
@click.option('-n', '--node', default="", help="Joule Node name")
@click.version_option()
@pass_config
def main(config, node):
    # create a Node structure for the name
    # if node_name is given use it, otherwise go with the default
    config.set_node_name(node)


main.add_command(admin)
main.add_command(streams)
main.add_command(data)
main.add_command(module)
main.add_command(folders)
main.add_command(proxies)
