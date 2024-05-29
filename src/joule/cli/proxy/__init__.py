import click
from joule.cli.lazy_group import LazyGroup

@click.group(name="proxy",
             cls=LazyGroup,
             lazy_subcommands={
                 "list": "joule.cli.proxy.list.cli_list",
                 "info": "joule.cli.proxy.info.cli_info"
             })
def proxies():
    """Proxied site information.

    Local URL's proxied by Joule.
    """
    pass  # pragma: no cover


