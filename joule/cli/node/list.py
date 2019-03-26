import click
from joule.cli.config import pass_config


@click.command(name="list")
@pass_config
def node_list(config):
    click.echo("TODO")
