import click

from joule.cli.lazy_group import LazyGroup

@click.group(name="archive",
             cls=LazyGroup,
             lazy_subcommands={"inspect": "joule.cli.archive.inspect.archive_inspect",
                               "upload": "joule.cli.archive.upload.archive_upload"})
def archive():
    """Manage Joule archives. See [archive docs] for more information on importing and
    exporting archive data"""
    pass  