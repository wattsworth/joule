import click
from .info import stream_info
from .list import stream_list
from .move import stream_move
from .destroy import stream_destroy


@click.group(name="stream")
def streams():
    """Manage Joule data streams"""
    pass


streams.add_command(stream_info)
streams.add_command(stream_list)
streams.add_command(stream_move)
streams.add_command(stream_destroy)
