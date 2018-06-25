import click

from joule.cmds.config import pass_config


@click.command(name="copy-data")
@click.argument("source")
@click.argument("destination")
@pass_config
def copy_data(config, source, destination):
    print("Copy %s to %s?" % (source, destination))