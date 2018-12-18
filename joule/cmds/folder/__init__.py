import click
from .move import folder_move
from .destroy import folder_destroy


@click.group(name="folder")
def folders():
    """Manage Joule folders"""
    pass  # pragma: no cover


folders.add_command(folder_move)
folders.add_command(folder_destroy)