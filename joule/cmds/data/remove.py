import click
import dateparser
import requests
from joule.cmds.config import pass_config


@click.command(name="remove")
@click.option("--start", help="timestamp or descriptive string")
@click.option("--end", help="timestamp or descriptive string")
@click.argument("stream")
@pass_config
def data_remove(config, start, end, stream):
    params = {"path": stream}
    if start is not None:
        params['start'] = int(dateparser.parse(start).timestamp() * 1e6)
    if end is not None:
        params['end'] = int(dateparser.parse(end).timestamp() * 1e6)
    resp = requests.delete(config.url+"/data", params=params)
    if resp.status_code != 200:
        click.echo("ERROR: "+resp.text, err=True)
    else:
        click.echo("OK")
