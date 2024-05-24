import click
from joule.cli.lazy_group import LazyGroup

@click.group(name="follower",
             cls=LazyGroup,
             lazy_subcommands={"list": "joule.cli.follower.list.cli_list",
                               "delete": "joule.cli.follower.delete.follower_delete"})
def follower():
    """Manage node followers."""
    pass  # pragma: no cover

