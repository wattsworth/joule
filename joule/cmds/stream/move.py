import click
import requests
from typing import Dict

from joule.cmds.config import pass_config


@click.command(name="move")
@click.argument("stream")
@click.argument("destination")
@pass_config
def move_stream(config, stream, destination):
    data = {
        "path": stream,
        "destination": destination
    }
    _post(config.url+"/stream/move.json", data=data)
    click.echo("OK")


def _post(url: str, data) -> Dict:
    resp = None  # to appease type checker
    try:
        resp = requests.put(url, data=data)
    except requests.ConnectionError:
        print("Error contacting Joule server at [%s]" % url)
        exit(1)
    if resp.status_code != 200:
        print("Error [%d]: %s" % (resp.status_code, resp.text))
        exit(1)
    return resp.json()
