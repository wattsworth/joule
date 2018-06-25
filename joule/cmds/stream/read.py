import click

from joule.cmds.config import pass_config


@click.command(name="read-data")
@click.argument("stream")
@pass_config
def read_data(config, stream):
    print("Extract data from %s" % (stream))