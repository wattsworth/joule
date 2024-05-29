import click

from joule.cli.lazy_group import LazyGroup

@click.group(name="stream",
             cls=LazyGroup,
             lazy_subcommands={
                 "info": "joule.cli.stream.info.cli_info",
                 "move": "joule.cli.stream.move.cli_move",
                 "delete": "joule.cli.stream.destroy.cli_delete",
                 "annotations": "joule.cli.stream.annotation.cli_annotations",
                 "rename": "joule.cli.stream.rename.cli_rename"
             })
def streams():
    """Manage data streams."""
    pass  # pragma: no cover



