import click
from .list import cli_list
from .delete import follower_delete


@click.group(name="follower")
def follower():
    pass  # pragma: no cover


follower.add_command(cli_list)
follower.add_command(follower_delete)
