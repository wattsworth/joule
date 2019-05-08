import click
import asyncio
from joule.cli.config import pass_config
from joule import errors, api


@click.command(name="add")
@click.argument("name")
@click.argument("url")
@click.argument("key")
@pass_config
def node_add(config, name, url, key):

    loop = asyncio.get_event_loop()
    my_node = None
    try:
        my_node = api.TcpNode(name, url, key)
        api.save_node(my_node)
        click.echo("Added [%s] to authorized nodes" % name)
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        if my_node is not None:
            loop.run_until_complete(
                my_node.close())
        loop.close()
