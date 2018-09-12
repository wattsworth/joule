import click
from joule.cmds import info, streams, data, module, folders, pass_config


@click.group()
@click.option('-u', '--url', default="http://localhost:8088", help="Joule Server")
@click.version_option(version=0.9)
@pass_config
def main(config, url):
    config.url = url


main.add_command(info)
main.add_command(streams)
main.add_command(data)
main.add_command(module)
main.add_command(folders)
