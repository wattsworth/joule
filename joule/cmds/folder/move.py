import click

from joule.cmds import helpers
from joule.cmds.config import pass_config
from joule.errors import ConnectionError


@click.command(name="move")
@click.argument("folder")
@click.argument("destination")
@pass_config
def folder_move(config, folder, destination):
    data = {
        "path": folder,
        "destination": destination
    }
    try:
        helpers.post_json(config.url+"/folder/move.json", data=data)
    except ConnectionError as e:
        raise click.ClickException(str(e)) from e
    click.echo("OK")


