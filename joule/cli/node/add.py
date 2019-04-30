import click
import asyncio
from joule.cli.config import pass_config
from joule.api import node
from joule import errors


@click.command(name="add")
@click.argument("url")
@click.argument("key")
@pass_config
def node_add(config, url, key):

    loop = asyncio.get_event_loop()
    my_node = None
    try:
        my_node = node.create_tcp_node(url, key)
        loop.run_until_complete(node.save(my_node))
        click.echo("Added [%s] to authorized nodes" % config.name)
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        if my_node is not None:
            loop.run_until_complete(
                my_node.close())
        loop.close()
