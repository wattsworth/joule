import click
import requests
from joule.cmds.config import pass_config


@click.command(name="destroy")
@click.argument("stream")
@pass_config
def stream_destroy(config, stream):
    click.confirm("Destroy stream [%s]?" % stream, abort=True)
    resp = requests.delete(config.url+"/stream.json", params={"path": stream})
    if resp.status_code != 200:
        click.echo("ERROR: "+resp.text, err=True)
    else:
        click.echo("OK")
