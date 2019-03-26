import click
from joule.cli.config import pass_config


@click.command(name="default")
@pass_config
def node_default(config):
    click.echo("TODO")
