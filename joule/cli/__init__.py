import click

from joule.cli.stream import streams
from joule.cli.data import data
from joule.cli.module import module
from joule.cli.folder import folders
from joule.cli.proxy import proxies
from joule.cli.root import info, initialize
from joule.cli.config import Config, pass_config


@click.group()
@click.option('-u', '--url', default="http://localhost:8088", help="Joule Server")
@click.version_option()
@pass_config
def main(config, url):
    config.url = url


main.add_command(info)
main.add_command(initialize)
main.add_command(streams)
main.add_command(data)
main.add_command(module)
main.add_command(folders)
main.add_command(proxies)