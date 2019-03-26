import click
from joule.cli.config import pass_config


@click.command(name="delete")
@pass_config
def master_delete(config):
    click.echo("TODO")