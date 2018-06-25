import click
from joule.cmds import streams, pass_config


@click.group()
@click.option('--url', default="http://localhost:8088", help="Joule Server")
@pass_config
def main(config, url):
    config.url = url


main.add_command(streams)
