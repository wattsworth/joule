import click

from joule.cli.lazy_group import LazyGroup

@click.group(name="admin",
             cls=LazyGroup,
             lazy_subcommands={"initialize": "joule.cli.admin.initialize.admin_initialize",
                               "erase": "joule.cli.admin.erase.admin_erase",
                               "authorize": "joule.cli.admin.authorize.admin_authorize",
                               "backup": "joule.cli.admin.backup.admin_backup",
                               "ingest": "joule.cli.admin.ingest.admin_ingest"})
def admin():
    """Administer the local node."""
    pass  # pragma: no cover