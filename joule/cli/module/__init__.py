import click
from .list import cli_list
from .info import cli_info
from .logs import cli_logs


@click.group(name="module")
def module():
    pass  # pragma: no cover


module.add_command(cli_list)
module.add_command(cli_info)
module.add_command(cli_logs)
