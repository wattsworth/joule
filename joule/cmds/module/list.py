import click
import requests
from tabulate import tabulate
from typing import Dict

from joule.cmds.config import pass_config
from joule.models import module


@click.command(name="list")
@pass_config
def module_list(config):
    json = _get(config.url + "/modules.json")
    result = []
    for item in json:
        inputs = '\n'.join(item['inputs'].values())
        outputs = '\n'.join(item['outputs'].values())
        stats = item['statistics']
        result.append([item['name'], inputs, outputs, stats['cpu_percent']*100.0, stats['memory'] / 2 ** 10])
    click.echo(tabulate(result,
                        headers=['Name', 'Inputs', 'Outputs', 'CPU %', "Mem (KiB)"],
                        tablefmt="fancy_grid"))


def _get(url: str, params=None) -> Dict:
    resp = None  # to appease type checker
    try:
        resp = requests.get(url, params=params)
    except requests.ConnectionError:
        print("Error contacting Joule server at [%s]" % url)
        exit(1)
    if resp.status_code != 200:
        print("Error [%d]: %s" % (resp.status_code, resp.text))
        exit(1)
    return resp.json()
