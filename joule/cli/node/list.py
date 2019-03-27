import click
from tabulate import tabulate
from joule.cli.config import pass_config
from joule.cli.helpers import get_node_configs, get_default_node


@click.command(name="list")
@pass_config
def node_list(config):
    try:
        node_configs = get_node_configs()
        default_node = get_default_node(node_configs)
    except ValueError as e:
        raise click.ClickException(str(e))
    result = []
    default_indicator = click.style("\u25CF", fg="green")
    for node in node_configs.values():
        if default_node.name == node.name:
            name = default_indicator + " " + node.name
        else:
            name = node.name
        result.append([name, node.url])
    if len(result) == 0:
        click.echo("No nodes available, add a node with [joule admin authorize] or [joule master add]")
        return
    click.echo("List of authorized nodes ("+default_indicator+"=default)")
    click.echo(tabulate(result,
                        headers=["Node", "URL"],
                        tablefmt="fancy_grid"))
