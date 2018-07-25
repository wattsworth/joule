import click
import requests
from typing import Dict

from joule.cmds.helpers import get_json
from joule.cmds.config import pass_config


@click.command(name="logs")
@click.argument("name")
@pass_config
def module_logs(config, name):
    payload = {'name': name}
    json = get_json(config.url + "/module/logs.json", params=payload)
    for item in json:
        click.echo(item)
