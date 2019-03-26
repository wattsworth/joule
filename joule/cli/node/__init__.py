import click
from .info import node_info
from .list import node_list
from .add import node_add
from .delete import node_delete
from .default import node_default


@click.group(name="node")
def node():
    pass  # pragma: no cover


node.add_command(node_info)
node.add_command(node_list)
node.add_command(node_add)
node.add_command(node_delete)
node.add_command(node_default)
