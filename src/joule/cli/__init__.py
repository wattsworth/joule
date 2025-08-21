import click

from joule.cli.config import Config, pass_config
from joule.cli.lazy_group import LazyGroup
from joule.version import version as joule_version

@click.group(
    cls=LazyGroup,
    lazy_subcommands={
        "data": "joule.cli.data.data",
        "stream": "joule.cli.stream.streams",
        "module": "joule.cli.module.module",
        "folder": "joule.cli.folder.folders",
        "proxy": "joule.cli.proxy.proxies",
        "admin": "joule.cli.admin.admin",
        "master": "joule.cli.master.master",
        "follower": "joule.cli.follower.follower",
        "event": "joule.cli.event.events",
        "node": "joule.cli.node.node",
        "archive": "joule.cli.archive.archive"
        }
)
@click.option('-n', '--node', default="", help="Joule Node name")
@click.version_option(version=joule_version)
@pass_config
def main(config, node):
    # create a Node structure for the name
    # if node_name is given use it, otherwise go with the default
    config.set_node_name(node)

