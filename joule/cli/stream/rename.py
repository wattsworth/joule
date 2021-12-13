import click
import asyncio

from joule import errors
from joule.cli.config import Config, pass_config
from joule.api import BaseNode


@click.command(name="rename")
@click.argument("stream")
@click.argument("name")
@pass_config
def cli_rename(config: Config, stream, name):
    """Rename a data stream."""
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(
            _run(config.node, stream, name))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        loop.run_until_complete(
            config.close_node())
        loop.close()
    click.echo("OK")


async def _run(node: BaseNode, stream_path: str, name: str):
    stream = await node.data_stream_get(stream_path)
    stream.name = name
    await node.data_stream_update(stream)
