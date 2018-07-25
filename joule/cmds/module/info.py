import click
import requests
from typing import Dict

from joule.cmds.helpers import get_json
from joule.cmds.config import pass_config


@click.command(name="info")
@click.argument("name")
@pass_config
def module_info(config, name):
    payload = {'name': name}
    json = get_json(config.url + "/module.json", params=payload)
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

