import click
import asyncio
from joule.cli.config import pass_config
from joule import errors, utilities
from joule.api import TcpNode, save_node

@click.command(name="add")
@click.argument("name")
@click.argument("url")
@click.argument("key")
@pass_config
def node_add(config, name: str, url: str, key: str):
    """Add a new node (requires API key)

    Use the information provided by 'joule master add user' """
    my_node = None
    try:
        if not url.startswith("http"):
            orig_url = url
            url = asyncio.run(
                utilities.misc.detect_url(url, 8088))
            if url is None:
                raise click.ClickException(
                    f"unable to contact [{orig_url}], node not added")
        my_node = TcpNode(name, url, key)
        save_node(my_node)
        click.echo("Added [%s] to authorized nodes" % name)
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        if my_node is not None:
            asyncio.run(
                my_node.close())
        
