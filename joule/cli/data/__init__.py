import click
from .copy import data_copy
from .read import cmd as data_read
from .remove import data_remove
from .intervals import intervals


@click.group(name="data")
def data():
    """Manage Joule data"""
    pass  # pragma: no cover


data.add_command(data_copy)
data.add_command(data_read)
data.add_command(data_remove)
data.add_command(intervals)
