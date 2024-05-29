import click

from joule.cli.lazy_group import LazyGroup

@click.group(name="module",
             cls=LazyGroup,
             lazy_subcommands={
                 "list": "joule.cli.module.list.cli_list",
                 "info": "joule.cli.module.info.cli_info",
                 "logs": "joule.cli.module.logs.cli_logs"
             })
def module():
    """Retrieve module information."""
    pass  # pragma: no cover

