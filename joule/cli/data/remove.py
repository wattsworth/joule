import click
import dateparser
import requests
from joule.cli.config import pass_config


@click.command(name="remove")
@click.option("--start", "-s" "start", help="timestamp or descriptive string")
@click.option("--end", "-e", "end", help="timestamp or descriptive string")
@click.option("--all", is_flag=True, help="remove all data")
@click.argument("stream")
@pass_config
def data_remove(config, start, end, all, stream):
    params = {"path": stream}
    if all:
        if start is not None or end is not None:
            raise click.ClickException("ERROR: specify either --all or --start/--end")
        params['all'] = '1'
    else:
        params['all'] = '0'
    if start is not None:
        params['start'] = int(dateparser.parse(start).timestamp() * 1e6)
    if end is not None:
        params['end'] = int(dateparser.parse(end).timestamp() * 1e6)
    try:
        resp = requests.delete(config.url + "/data", params=params)
    except requests.ConnectionError:
        raise click.ClickException("Error contacting Joule server at [%s]" % config.url)
    if resp.status_code != 200:
        raise click.ClickException("Error [%d]: %s" % (resp.status_code, resp.text))
    else:
        click.echo("OK")
