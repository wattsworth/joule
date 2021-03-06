import click
import asyncio
import argparse

import joule.errors
from joule.utilities.interval_tools import interval_intersection
from joule import errors
from joule.cli.config import Config, pass_config
from joule.utilities import timestamp_to_human, human_to_timestamp
from joule.client.builtins.merge_filter import MergeFilter


@click.command(name="merge")
@click.option("--start", help="timestamp or descriptive string")
@click.option("--end", help="timestamp or descriptive string")
@click.option('-p', "--primary", help="primary stream", required=True)
@click.option('-s', "--secondary", multiple=True, help="secondary stream")
@click.option('-d', "--destination", help="destination stream", required=True)
@pass_config
def merge(config: Config, start, end, primary, secondary, destination):
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
        loop.run_until_complete(_run(start, end, destination, primary, secondary, config.node))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        loop.run_until_complete(
            config.close_node())
        loop.close()


async def _run(start, end, destination, primary, secondaries, node):
    # --- RETRIEVE SOURCE STREAMS ---
    # prints out error messages if the source streams do not exist
    try:
        primary_stream: joule.DataStream = await node.data_stream_get(primary.split(':')[0])
    except joule.errors.ApiError as e:
        raise click.ClickException(f"Primary stream {primary}: {str(e)}")
    secondary_streams = []
    for s in secondaries:
        try:
            s_stream = await node.data_stream_get(s.split(':')[0])
            secondary_streams.append(s_stream)
        except joule.errors.ApiError as e:
            raise click.ClickException(f"Secondary stream {s}: {str(e)}")

    # --- CHECK FOR DESTINATION STREAM ---
    destination_width = len(primary_stream.elements)
    for s in secondary_streams:
        destination_width += len(s.elements)
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

    click.echo(f"Primary Stream: \n\t{primary}")
    click.echo(f"Secondary Streams: \n\t{', '.join(s for s in secondaries)}")
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
        elements = []
        # check for a primary prefix
        prefix = ""
        if ':' in primary:
            prefix = primary.split(':')[-1]
        for e in primary_stream.elements:
            e.name = prefix + e.name
            elements.append(e)
        for i in range(len(secondaries)):
            prefix = ""
            if ':' in secondaries[i]:
                prefix = secondaries[i].split(':')[-1]
            for e in secondary_streams[i].elements:
                e.name = prefix + e.name
                elements.append(e)
        dest_stream = joule.api.DataStream(name=dest_name, elements=elements, datatype='float32')
        try:
            dest_stream = await node.data_stream_create(dest_stream, '/'.join(dest_path))
        except joule.errors.ApiError as e:
            raise click.ClickException(f"Creating destination: {str(e)}")

    # --- READY TO GO ---
    common_intervals = await node.data_intervals(primary_stream, start=start, end=end)
    for s in secondary_streams:
        s_intervals = await node.data_intervals(s, start=start, end=end)
        common_intervals = interval_intersection(common_intervals, s_intervals)
    for interval in common_intervals:
        start = interval[0]
        end = interval[1]
        click.echo("Processing [%s] -> [%s]" % (timestamp_to_human(start), timestamp_to_human(end)))
        merge_filter = MergeFilter()
        inputs = {'primary': await node.data_read(primary_stream, start, end)}
        for i in range(len(secondary_streams)):
            inputs[f"secondary_{i}"] = await node.data_read(secondary_streams[i], start, end)
        outputs = {'destination': await node.data_write(dest_stream, start, end)}
        args = argparse.Namespace(primary="primary")
        await merge_filter.run(args, inputs, outputs)
        await outputs['destination'].close()
