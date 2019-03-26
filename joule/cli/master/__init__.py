import click
from .list import master_list
from .delete import master_delete
from .add import master_add


@click.group(name="master")
def master():
    pass  # pragma: no cover


master.add_command(master_list)
master.add_command(master_add)
master.add_command(master_delete)
