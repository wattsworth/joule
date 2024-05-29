import click
from joule.cli.lazy_group import LazyGroup

@click.group(name="node",
             cls=LazyGroup,
             lazy_subcommands={
                 "info": "joule.cli.node.info.node_info",
                 "list": "joule.cli.node.list.node_list",
                 "add": "joule.cli.node.add.node_add",
                 "delete": "joule.cli.node.delete.node_delete",
                 "default": "joule.cli.node.default.node_default"
             })
def node():
    """Configure local settings."""
    pass  # pragma: no cover

