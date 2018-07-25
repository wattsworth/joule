import click
import requests
from typing import Dict

from joule.cmds.config import pass_config


@click.command(name="info")
@click.argument("name")
@pass_config
def module_info(config, name):
    payload = {'name': name}
    json = _get(config.url + "/module.json", params=payload)
    # display module information
    click.echo()
    click.echo("Name:         %s" % json['name'])
    click.echo("Description:  %s" % json['description'])
    click.echo("Inputs:")
    if len(json['inputs']) == 0:
        click.echo("\t--none--")
    else:
        for (name, loc) in json['inputs'].items():
            click.echo("\t%s:\t%s" % (name, loc))
    click.echo("Outputs:")
    if len(json['outputs']) == 0:
        click.echo("\t--none--")
    else:
        for (name, loc) in json['outputs'].items():
            click.echo("\t%s:\t%s" % (name, loc))


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
    try:
        return resp.json()
    except ValueError:
        click.echo("Error: Invalid server response, check the URL")
        exit(1)