import click
from .list import cli_list
from .info import cli_info


@click.group(name="proxy")
def proxies():
    """Proxied site information.

    Local URL's proxied by Joule.
    """
    pass  # pragma: no cover


proxies.add_command(cli_list)
proxies.add_command(cli_info)
