import click
from .list import cli_list
from .info import cli_info


@click.group(name="proxy")
def proxies():
    pass  # pragma: no cover


proxies.add_command(cli_list)
proxies.add_command(cli_info)
