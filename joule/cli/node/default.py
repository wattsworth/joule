import click
from joule.cli.config import pass_config
from joule.api import node


@click.command(name="default")
@click.argument("name")
@pass_config
def node_default(config, name):
    try:
        node.set_default(name)
        click.echo("Set [%s] as the default node" % name)
    except ValueError as e:
        raise click.ClickException(str(e))
