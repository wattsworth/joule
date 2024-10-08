import click
from joule.cli.config import pass_config
from joule.api import delete_node
from joule import errors


@click.command(name="delete")
@click.argument("name")
@pass_config
def node_delete(config, name):
    """Remove a node."""
    try:
        delete_node(name)
    except errors.ApiError as e:
        raise click.ClickException(str(e))
    click.echo("Removed [%s] from nodes" % name)
