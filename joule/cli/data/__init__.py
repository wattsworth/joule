import click
from .copy import data_copy
from .read import cmd as data_read
from .remove import data_remove
from .intervals import intervals
from .consolidate import consolidate
from .merge import merge
from .mean import mean
from .median import median
from .ingest import ingest

@click.group(name="data")
def data():
    """Interact with data streams."""
    pass  # pragma: no cover

@click.group(name="filter")
def filter():
    """Filter stream data."""
    pass  # pragma: no cover

data.add_command(data_copy)
data.add_command(merge)
data.add_command(data_read)
data.add_command(data_remove)
data.add_command(intervals)
data.add_command(consolidate)
data.add_command(ingest)
data.add_command(filter)

filter.add_command(mean)
filter.add_command(median)
