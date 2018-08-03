import click
from joule.cmds import streams, data, module, pass_config


@click.group()
@click.option('-u', '--url', default="http://localhost:8088", help="Joule Server")
@pass_config
def main(config, url):
    config.url = url


main.add_command(streams)
main.add_command(data)
main.add_command(module)
