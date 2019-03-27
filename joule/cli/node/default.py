import click
from joule.cli.config import pass_config
from joule.cli.helpers import set_default_node


@click.command(name="default")
@click.argument("name")
@pass_config
def node_default(config, name):
    try:
        set_default_node(name)
        click.echo("Set [%s] as the default node" % name)
    except ValueError as e:
        raise click.ClickException(str(e))
