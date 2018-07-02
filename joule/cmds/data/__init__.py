import click
from .copy import data_copy
from .read import data_read
from .remove import data_remove


@click.group(name="data")
def data():
    """Manage Joule data"""
    pass


data.add_command(data_copy)
data.add_command(data_read)
data.add_command(data_remove)
