import click
import requests
from joule.cli.config import pass_config
from joule.utilities import human_to_timestamp

@click.command(name="delete")
@click.option("-s", "--start", "start", help="timestamp or descriptive string")
@click.option("-e", "--end", "end", help="timestamp or descriptive string")
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
        try:
            params['start'] = human_to_timestamp(start)
        except ValueError:
            raise click.ClickException("invalid start time: [%s]" % start)
    if end is not None:
        try:
            params['end'] = human_to_timestamp(end)
        except ValueError:
            raise click.ClickException("invalid end time: [%s]" % end)
    try:
        resp = requests.delete(config.url + "/data", params=params)
    except requests.ConnectionError:
        raise click.ClickException("Error contacting Joule server at [%s]" % config.url)
    if resp.status_code != 200:
        raise click.ClickException("Error [%d]: %s" % (resp.status_code, resp.text))
    else:
        click.echo("OK")
