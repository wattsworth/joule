import click

from joule.cli.lazy_group import LazyGroup

@click.group(name="event",
             cls=LazyGroup,
             lazy_subcommands={
                 "info": "joule.cli.event.info.cli_info",
                 "move": "joule.cli.event.move.cli_move",
                 "rename": "joule.cli.event.rename.cli_rename",
                 "copy": "joule.cli.event.copy.cli_copy",
                 "remove": "joule.cli.event.remove.cli_remove"
             })
def events():
    """Manage event streams."""
    pass  

