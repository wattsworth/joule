import click

from joule.cmds.config import pass_config


@click.command(name="destroy")
@click.argument("source")
@click.argument("destination")
@pass_config
def destroy_stream(config, stream):
    print("Destroy stream %s?" % (stream))
