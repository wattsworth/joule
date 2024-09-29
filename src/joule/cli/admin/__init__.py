import click

from joule.cli.lazy_group import LazyGroup

@click.group(name="admin",
             cls=LazyGroup,
             lazy_subcommands={"initialize": "joule.cli.admin.initialize.admin_initialize",
                               "erase": "joule.cli.admin.erase.admin_erase",
                               "authorize": "joule.cli.admin.authorize.admin_authorize"})
def admin():
    """Administer the local node."""
    pass  