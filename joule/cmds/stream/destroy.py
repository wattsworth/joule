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
        raise click.ClickException("Error [%d]: %s" % (resp.status_code, resp.text))
    else:
        click.echo("OK")
