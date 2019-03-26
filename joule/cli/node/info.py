import click
from joule.cli.config import pass_config


@click.command(name="info")
@pass_config
def node_info(config):
    click.echo("TODO")
