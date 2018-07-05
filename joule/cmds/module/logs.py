import click
import requests
from typing import Dict

from joule.cmds.config import pass_config


@click.command(name="logs")
@click.argument("name")
@pass_config
def module_logs(config, name):
    payload = {'name': name}
    json = _get(config.url + "/module/logs.json", params=payload)
    for item in json:
        click.echo(item)


def _get(url: str, params=None) -> Dict:
    resp = None  # to appease type checker
    try:
        resp = requests.get(url, params=params)
    except requests.ConnectionError:
        print("Error contacting Joule server at [%s]" % url)
        exit(1)
    if resp.status_code != 200:
        print("Error [%d]: %s" % (resp.status_code, resp.text))
        exit(1)
    return resp.json()