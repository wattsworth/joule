import click

from joule.cmds import helpers
from joule.cmds.config import pass_config


@click.command(name="move")
@click.argument("folder")
@click.argument("destination")
@pass_config
def folder_move(config, folder, destination):
    data = {
        "path": folder,
        "destination": destination
    }
    helpers.post_json(config.url+"/folder/move.json", data=data)
    click.echo("OK")


