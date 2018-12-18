import click
import requests
from typing import Dict

from joule.cmds.helpers import get_json
from joule.cmds.config import pass_config
from joule.errors import ConnectionError


@click.command(name="info")
@click.argument("name")
@pass_config
def module_info(config, name):
    payload = {'name': name}
    try:
        json = get_json(config.url + "/module.json", params=payload)
    except ConnectionError as e:
        raise click.ClickException(str(e)) from e
    # display module information
    click.echo()
    click.echo("Name:\n\t%s" % json['name'])
    click.echo("Description:\n\t%s" % json['description'])
    if json['has_interface']:
        click.echo("Interface URL:\n\t%s/interface/%d/" % (config.url, json['id']))
    click.echo("Inputs:")
    if len(json['inputs']) == 0:
        click.echo("\t--none--")
    else:
        for (name, loc) in json['inputs'].items():
            click.echo("\t%s: %s" % (name, loc))
    click.echo("Outputs:")
    if len(json['outputs']) == 0:
        click.echo("\t--none--")
    else:
        for (name, loc) in json['outputs'].items():
            click.echo("\t%s:\t%s" % (name, loc))


