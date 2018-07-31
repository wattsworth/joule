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
        result.append([item['name'], inputs, outputs, stats['cpu_percent']*100.0, stats['memory'] / 2 ** 10])
    click.echo(tabulate(result,
                        headers=['Name', 'Inputs', 'Outputs', 'CPU %', "Mem (KiB)"],
                        tablefmt="fancy_grid"))
