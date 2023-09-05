import click
from .info import cli_info
from .move import cli_move
from .destroy import cli_delete
from .annotation import cli_annotations
from .rename import cli_rename


@click.group(name="stream")
def streams():
    """Manage data streams."""
    pass  # pragma: no cover


streams.add_command(cli_info)
streams.add_command(cli_move)
streams.add_command(cli_delete)
streams.add_command(cli_annotations)
streams.add_command(cli_rename)
