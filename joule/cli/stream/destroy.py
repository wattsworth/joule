import click
import asyncio

from joule import errors
from joule.cli.config import pass_config


@click.command(name="delete")
@click.argument("stream")
@pass_config
def cli_delete(config, stream):
    """Delete a data stream"""
    # make sure the stream exists
    asyncio.run(run(config, stream))


async def run(config, stream):
    stream_type = None
    try:
        await config.node.data_stream_get(stream)
        stream_type = "data"
    except errors.ApiError:
        pass
    try:
        if stream_type is None:
            await config.node.event_stream_get(stream)
            stream_type = "event"
    except errors.ApiError:
        pass
    if stream_type is None:
        await config.close_node()
        raise click.ClickException("Stream does not exist")

    if not click.confirm("Delete %s stream [%s]?" % (stream_type, stream)):
        click.echo("Cancelled")
        await config.close_node()
        return

    try:
        if stream_type == 'data':
            await config.node.data_stream_delete(stream)
        elif stream_type == 'event':
            await config.node.event_stream_delete(stream)
        else:
            raise click.ClickException("unknown stream type [%s]" % stream_type)
        click.echo("OK")

    except errors.ApiError as e:
        raise click.ClickException(str(e))
    finally:
        await config.close_node()
