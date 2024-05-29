import click
#from .copy import data_copy
#from .read import cmd as data_read
#from .remove import data_remove
#from .intervals import intervals
#from .consolidate import consolidate
#from .merge import merge
#from .mean import mean
#from .median import median
#from .ingest import ingest
from joule.cli.lazy_group import LazyGroup

@click.group(name="data",
             cls=LazyGroup,
             lazy_subcommands={"copy": "joule.cli.data.copy.data_copy",
                               "read": "joule.cli.data.read.cmd",
                               "delete": "joule.cli.data.delete.data_delete",
                               "intervals": "joule.cli.data.intervals.intervals",
                               "consolidate": "joule.cli.data.consolidate.consolidate",
                               "merge": "joule.cli.data.merge.merge",
                               "ingest": "joule.cli.data.ingest.ingest"})
def data():
    """Interact with data streams."""
    pass  # pragma: no cover

@click.group(name="filter",
             cls=LazyGroup,
             lazy_subcommands={"mean": "joule.cli.data.mean",
                               "median": "joule.cli.data.median"})
def filter():
    """Filter stream data."""
    pass  # pragma: no cover

data.add_command(filter)

"""
data.add_command(data_copy)
data.add_command(merge)
data.add_command(data_read)
data.add_command(data_remove)
data.add_command(intervals)
data.add_command(consolidate)
data.add_command(ingest)

filter.add_command(mean)
filter.add_command(median)
"""