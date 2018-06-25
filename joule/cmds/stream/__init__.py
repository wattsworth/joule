import click
from .info import stream_info
from .list import list_streams


@click.group(name="stream")
def streams():
    pass


streams.add_command(stream_info, name="info")
streams.add_command(list_streams, name="list")
