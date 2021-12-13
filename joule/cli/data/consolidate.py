import click
import asyncio

from joule import errors
from joule.cli.config import Config, pass_config
from joule.utilities import timestamp_to_human, human_to_timestamp


@click.command(name="consolidate")
@click.option('-s', "--start", help="timestamp or descriptive string")
@click.option('-e', "--end", help="timestamp or descriptive string")
@click.option('-m', "--max-gap", help="remove intervals shorter than this (in us)", default=2e6)
@click.argument("stream")
@pass_config
def consolidate(config: Config, start, end, max_gap, stream: str):
    """Remove gaps in a data stream."""
    if start is not None:
        try:
            start = human_to_timestamp(start)
        except ValueError:
            raise click.ClickException("invalid start time: [%s]" % start)
    if end is not None:
        try:
            end = human_to_timestamp(end)
        except ValueError:
            raise click.ClickException("invalid end time: [%s]" % end)

    loop = asyncio.get_event_loop()
    try:
        num_removed = loop.run_until_complete(config.node.data_consolidate(stream, max_gap, start, end))
        if num_removed > 0:
            print("Consolidated %d intervals" % num_removed)
        else:
            print("No intervals less than %d us" % max_gap)
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        loop.run_until_complete(
            config.close_node())
        loop.close()
