import click
from .list import cli_list
from .delete import cli_delete
from .add import cli_add


@click.group(name="master")
def master():
    pass  # pragma: no cover


master.add_command(cli_list)
master.add_command(cli_delete)
master.add_command(cli_add)
