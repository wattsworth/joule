import click
from .list import module_list
from .info import module_info
from .logs import module_logs

@click.group(name="module")
def module():
    pass


module.add_command(module_list)
module.add_command(module_info)
module.add_command(module_logs)