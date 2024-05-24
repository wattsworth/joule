import click
from joule.cli.lazy_group import LazyGroup

@click.group(name="master",
             cls=LazyGroup,
             lazy_subcommands={"list": "joule.cli.master.list.cli_list",
                               "delete": "joule.cli.master.delete.cli_delete",
                               "add": "joule.cli.master.add.cli_add"})
def master():
    """Manage node access."""
    pass  # pragma: no cover

