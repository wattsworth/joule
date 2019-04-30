import click
from tabulate import tabulate
from joule.cli.config import pass_config
from joule.api import node


@click.command(name="list")
@pass_config
def node_list(config):
    nodes = node.get_all()
    default_node = node.get()
    result = []
    default_indicator = click.style("\u25CF", fg="green")
    for my_node in nodes:
        if default_node.name == my_node.name:
            name = default_indicator + " " + my_node.name
        else:
            name = node.name
        result.append([name, node.url])
    if len(result) == 0:
        click.echo("No nodes available, add a node with [joule admin authorize] or [joule node add]")
        return
    click.echo("List of authorized nodes ("+default_indicator+"=default)")
    click.echo(tabulate(result,
                        headers=["Node", "URL"],
                        tablefmt="fancy_grid"))
