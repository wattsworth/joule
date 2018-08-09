import click
import requests
from typing import Dict

from joule.cmds.config import pass_config
from joule.cmds import helpers


@click.command(name="move")
@click.argument("stream")
@click.argument("destination")
@pass_config
def stream_move(config, stream, destination):
    data = {
        "path": stream,
        "destination": destination
    }
    helpers.post_json(config.url+"/stream/move.json", data=data)
    click.echo("OK")
