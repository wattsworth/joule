import click
import asyncio
import argparse

import joule.errors
from joule import errors
from joule.cli.config import Config, pass_config
from joule.utilities import timestamp_to_human, human_to_timestamp
from joule.client.builtins.mean_filter import MeanFilter


@click.command(name="mean")
@click.argument("source")
@click.argument("destination")
@click.option("-w", "--window", help="window size", required=True, type=int)
@click.option("--start", help="timestamp or descriptive string")
@click.option("--end", help="timestamp or descriptive string")
@pass_config
def mean(config: Config, start, end, source, destination, window):
    """Apply a moving average (mean) filter."""
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

    try:
        asyncio.run(_run(start, end, source, destination, window, config.node))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        asyncio.run(
            config.close_node())


async def _run(start, end, source, destination, window, node):
    # --- RETRIEVE SOURCE STREAMS ---
    # prints out error messages if the source streams do not exist
    try:
        source_stream: joule.DataStream = await node.data_stream_get(source)
    except joule.errors.ApiError as e:
        raise click.ClickException(f"Source stream {source}: {str(e)}")

    # --- CHECK FOR DESTINATION STREAM ---
    destination_width = len(source_stream.elements)
    dest_exists = True
    dest_stream = None  # this is set below, or created later
    try:
        dest_stream = await node.data_stream_get(destination)
        if len(dest_stream.elements) != destination_width:
            raise click.ClickException(f"Destination must have {destination_width} elements")
        if not dest_stream.datatype.startswith('float'):
            raise click.ClickException(f"Destination must be a float datatype")

    except joule.errors.ApiError as e:
        dest_exists = False
    click.echo("Mean filter with window size %d" % window)
    click.echo(f"Source Stream: \n\t{source}")
    if dest_exists:
        click.echo(f"Destination Stream: \n\t{destination}")
    else:
        click.echo(f"Creating Destination: \n\t{destination}")

    if not click.confirm("Proceed?"):
        click.echo("Cancelled")
        return

    if not dest_exists:
        # create the destination
        dest_path = destination.split('/')[:-1]
        dest_name = destination.split('/')[-1]

        dest_stream = joule.api.DataStream(name=dest_name,
                                           elements=source_stream.elements,
                                           datatype='float32')
        try:
            dest_stream = await node.data_stream_create(dest_stream, '/'.join(dest_path))
        except joule.errors.ApiError as e:
            raise click.ClickException(f"Creating destination: {str(e)}")

    # --- READY TO GO ---
    for interval in await node.data_intervals(source_stream, start=start, end=end):
        start = interval[0]
        end = interval[1]
        click.echo("Processing [%s] -> [%s]" % (timestamp_to_human(start), timestamp_to_human(end)))
        mean_filter = MeanFilter()
        inputs = {'input': await node.data_read(source_stream, start, end)}
        outputs = {'output': await node.data_write(dest_stream, start, end)}
        args = argparse.Namespace(window=window)
        await mean_filter.run(args, inputs, outputs)
        await outputs['output'].close()
