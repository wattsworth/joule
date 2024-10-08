import click
from joule.cli.config import pass_config
from joule.api import set_default_node
from joule.errors import ApiError

@click.command(name="default")
@click.argument("name")
@pass_config
def node_default(config, name):
    """Change the default node."""
    try:
        set_default_node(name)
        click.echo("Set [%s] as the default node" % name)
    except ApiError as e:
        raise click.ClickException(str(e))
