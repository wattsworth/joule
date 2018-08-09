import click
import requests
from joule.cmds.config import pass_config


@click.command(name="remove")
@click.option("--recursive", "-r", is_flag=True)
@click.argument("folder")
@pass_config
def folder_destroy(config, folder, recursive):
    params = {"path": folder}
    if recursive:
        params["recursive"] = True
    resp = requests.delete(config.url + "/folder.json", params=params)
    if resp.status_code != 200:
        click.echo("Error [%d]: %s" % (resp.status_code, resp.text))
        exit(1)
    else:
        click.echo("OK")
