import click
from joule.cli.config import pass_config
from joule.cli.helpers import get_node_configs, get_default_node, set_default_node, write_node_configs


@click.command(name="delete")
@click.argument("name")
@pass_config
def node_delete(config, name):
    node_configs = get_node_configs()
    default_node = get_default_node(node_configs)
    if name not in node_configs.keys():
        raise click.ClickException("Invalid node name, view nodes with [joule node list]")
    del node_configs[name]
    write_node_configs(node_configs)
    # if the default node is deleted pick another or clear it
    if default_node.name == name:
        set_default_node("")
    click.echo("Removed [%s] from nodes" % name)
