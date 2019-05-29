import click
import asyncio
from tabulate import tabulate

from joule import errors
from joule.api import BaseNode
from joule.cli.config import pass_config


@click.command(name="list")
@click.option('--statistics', '-s', is_flag=True, help="include memory and CPU statistics")
@pass_config
def cli_list(config, statistics):
    loop = asyncio.get_event_loop()

    try:
        loop.run_until_complete(
            _run(config.node, statistics))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        loop.run_until_complete(
            config.close_node())
        loop.close()


async def _run(node: BaseNode, statistics):
    modules = await node.module_list(statistics)
    # display module information
    headers = ['Name', 'Inputs', 'Outputs']
    if statistics:
        headers += ['CPU %', "Mem %"]
    result = []
    for module in modules:
        inputs = '\n'.join(module.inputs.values())
        outputs = '\n'.join(module.outputs.values())
        data = [module.name, inputs, outputs]
        if statistics:
            if module.statistics.cpu_percent is None:
                cpu_stat = "\u2014"
            else:
                cpu_stat = "%0.1f" % module.statistics.cpu_percent
            if module.statistics.memory_percent is None:
                mem_stat = "\u2014"
            else:
                mem_stat = '%0.1f' % module.statistics.memory_percent
            data += [cpu_stat, mem_stat]
        result.append(data)
    click.echo(tabulate(result,
                        headers=headers,
                        tablefmt="fancy_grid"))
