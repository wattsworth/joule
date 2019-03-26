import click
from joule.cli.config import pass_config


@click.command(name="add")
@pass_config
def node_add(config):
    click.echo("TODO")
