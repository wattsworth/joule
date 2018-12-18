import click
from tabulate import tabulate

from joule.cmds.helpers import get_json
from joule.cmds.config import pass_config
from joule.errors import ConnectionError


@click.command(name="list")
@click.option('--statistics', '-s', is_flag=True, help="include memory and CPU statistics")
@pass_config
def module_list(config, statistics):
    try:
        query = "/modules.json"
        if statistics:
            query += "?statistics=1"
        json = get_json(config.url + query)
    except ConnectionError as e:
        raise click.ClickException(str(e)) from e
    headers = ['Name', 'Inputs', 'Outputs']
    if statistics:
        headers += ['CPU %', "Mem %"]
    result = []
    for module in json:
        inputs = '\n'.join(module['inputs'].values())
        outputs = '\n'.join(module['outputs'].values())
        data = [module['name'], inputs, outputs]
        if statistics:
            stats = module['statistics']
            if stats['cpu_percent'] is None:
                cpu_stat = "\u2014"
            else:
                cpu_stat = "%0.1f" % float(stats['cpu_percent'])
            if stats['memory_percent'] is None:
                mem_stat = "\u2014"
            else:
                mem_stat = '%0.1f' % float(stats['memory_percent'])
            data += [cpu_stat, mem_stat]
        result.append(data)
    click.echo(tabulate(result,
                        headers=headers,
                        tablefmt="fancy_grid"))
