import click
from joule.cli.config import pass_config
from joule import api


@click.command(name="default")
@click.argument("name")
@pass_config
def node_default(config, name):
    try:
        api.set_default_node(name)
        click.echo("Set [%s] as the default node" % name)
    except ValueError as e:
        raise click.ClickException(str(e))
