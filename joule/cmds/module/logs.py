import click

from joule.cmds.helpers import get_json
from joule.cmds.config import pass_config
from joule.errors import ConnectionError


@click.command(name="logs")
@click.argument("name")
@pass_config
def module_logs(config, name):
    payload = {'name': name}
    try:
        json = get_json(config.url + "/module/logs.json", params=payload)
    except ConnectionError as e:
        raise click.ClickException(str(e)) from e
    for item in json:
        click.echo(item)
