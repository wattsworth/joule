import click
from .info import stream_info
from .list import list_streams
from .move import move_stream
from .remove import remove_data
from .destroy import destroy_stream
from .read import read_data
from .copy import copy_data


@click.group(name="stream")
def streams():
    """Manage Joule data streams"""
    pass


streams.add_command(stream_info)
streams.add_command(list_streams)
streams.add_command(move_stream)
streams.add_command(remove_data)
streams.add_command(destroy_stream)
streams.add_command(read_data)
streams.add_command(copy_data)