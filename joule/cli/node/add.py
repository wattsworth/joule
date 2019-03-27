import click
import asyncio
from joule.api.session import Session
from joule.api.node import node_info
from joule.cli.config import pass_config
from joule.cli.helpers import get_cafile, NodeConfig, get_node_configs, write_node_configs
from joule import errors


@click.command(name="add")
@click.argument("url")
@click.argument("key")
@pass_config
def node_add(config, url, key):

    loop = asyncio.get_event_loop()
    try:
        # create a session from the arguments and try to connect to the node
        session = Session(url, key, get_cafile())
        loop.run_until_complete(
            _run(session))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        loop.run_until_complete(
            session.close())
        loop.close()


async def _run(session: Session):
    info = await node_info(session)
    config = NodeConfig(info.name, session.url, session.key)
    node_configs = get_node_configs()
    node_configs[config.name] = config
    write_node_configs(node_configs)
    click.echo("Added [%s] to authorized nodes" % config.name)
