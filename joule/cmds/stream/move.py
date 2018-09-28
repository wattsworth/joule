import click

from joule.cmds.config import pass_config
from joule.cmds import helpers
from joule.errors import ConnectionError


@click.command(name="move")
@click.argument("stream")
@click.argument("destination")
@pass_config
def stream_move(config, stream, destination):
    data = {
        "path": stream,
        "destination": destination
    }
    try:
        helpers.post_json(config.url+"/stream/move.json", data=data)
    except ConnectionError as e:
        raise click.ClickException(str(e)) from e
    click.echo("OK")
