import click
import dateparser
import requests
from joule.cmds.config import pass_config


@click.command(name="remove")
@click.option("--from", "start", help="timestamp or descriptive string")
@click.option("--to", "end", help="timestamp or descriptive string")
@click.argument("stream")
@pass_config
def data_remove(config, start, end, stream):
    params = {"path": stream}
    if start is not None:
        params['start'] = int(dateparser.parse(start).timestamp() * 1e6)
    if end is not None:
        params['end'] = int(dateparser.parse(end).timestamp() * 1e6)
    try:
        resp = requests.delete(config.url+"/data", params=params)
    except requests.ConnectionError:
        click.echo("Error contacting Joule server at [%s]" % config.url)
        exit(1)
    if resp.status_code != 200:
        click.echo("Error [%d]: %s" % (resp.status_code, resp.text))
        exit(1)
    else:
        click.echo("OK")
