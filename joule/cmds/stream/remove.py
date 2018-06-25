import click

from joule.cmds.config import pass_config


@click.command(name="remove-data")
@click.argument("stream")
@pass_config
def remove_data(config, stream):
    print("Remove data from %s?" % (stream))