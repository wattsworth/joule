import click
from tabulate import tabulate

from joule.cmds.helpers import get_json
from joule.cmds.config import pass_config


@click.command(name="list")
@pass_config
def module_list(config):
    json = get_json(config.url + "/modules.json")
    result = []
    for item in json:
        inputs = '\n'.join(item['inputs'].values())
        outputs = '\n'.join(item['outputs'].values())
        stats = item['statistics']
        if stats['cpu_percent'] is None:
            cpu_stat = "\u2014"
        else:
            cpu_stat = "%0.1f" % float(stats['cpu_percent'])
        if stats['memory'] is None:
            mem_stat = "\u2014"
        else:
            mem_stat = stats['memory'] / 2 ** 10
        result.append([item['name'], inputs, outputs, cpu_stat, mem_stat])
    click.echo(tabulate(result,
                        headers=['Name', 'Inputs', 'Outputs', 'CPU %', "Mem (KiB)"],
                        tablefmt="fancy_grid"))
