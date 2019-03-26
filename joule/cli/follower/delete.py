import click
from joule.cli.config import pass_config


@click.command(name="delete")
@pass_config
def follower_delete(config):
    click.echo("TODO")
