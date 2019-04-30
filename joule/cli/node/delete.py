import click
from joule.cli.config import pass_config
from joule.api import node
from joule import errors


@click.command(name="delete")
@click.argument("name")
@pass_config
def node_delete(config, name):
    try:
        node.delete(name)
    except errors.ApiError as e:
        raise click.ClickException(str(e))
    click.echo("Removed [%s] from nodes" % name)
