import click
from .config import pass_config
from .helpers import get_json


@click.command(name="info")
@pass_config
def info(config):
    json = get_json(config.url + "/version.json")
    # display info
    click.echo("Server Version: %s" % json['version'])
    click.echo("Status: online")
