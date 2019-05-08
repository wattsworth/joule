import click
from tabulate import tabulate
from joule.cli.config import pass_config
from joule import api
from joule import errors


@click.command(name="list")
@pass_config
def node_list(config):
    try:
        nodes = api.get_nodes()
        default_node = api.get_node()
    except errors.ApiError as e:
        raise click.ClickException(str(e))

    result = []
    default_indicator = click.style("\u25CF", fg="green")
    for node in nodes:
        if default_node.name == node.name:
            name = default_indicator + " " + node.name
        else:
            name = node.name
        result.append([name, node.url])

    click.echo("List of authorized nodes ("+default_indicator+"=default)")
    click.echo(tabulate(result,
                        headers=["Node", "URL"],
                        tablefmt="fancy_grid"))
