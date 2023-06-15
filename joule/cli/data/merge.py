import click
import asyncio
import argparse

import joule.errors
from joule.utilities.interval_tools import interval_intersection, interval_difference
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
    """Merge two or more data streams. Elements will be prefixed with source stream name or a custom prefix
       using a : such as /source/streamA would create elements streamA E1, streamA E2, etc and /source/streamA:A
       would create elements A E1, A E2, etc"""
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
        asyncio.run(_run(start, end, destination, primary, secondary, config.node))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        asyncio.run(
            config.close_node())


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
        else:
            prefix = primary_stream.name
        for e in primary_stream.elements:
            e.name = prefix + ' ' + e.name
            elements.append(e)
        for i in range(len(secondaries)):
            prefix = ""
            if ':' in secondaries[i]:
                prefix = secondaries[i].split(':')[-1]
            else:
                prefix = secondary_streams[i].name
            for e in secondary_streams[i].elements:
                e.name = prefix +' '+ e.name
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
    copied_intervals = await node.data_intervals(dest_stream, start=start, end=end)
    # do not copy intervals that we already have
    pending_intervals = interval_difference(common_intervals, copied_intervals)
    # only copy intervals with at least 1 second of data- there are issues with 1 sample offsets
    # that cause merge to think there is missing data when there is not any- this is probably due to
    # the backend not having the data boundaries stored exactly correctly
    pending_intervals = [i for i in pending_intervals if (i[1]-i[0]) > 1e6]
    if len(pending_intervals) == 0:
        click.echo("Destination already has all the data, nothing to do")
    else:
        start_time = joule.utilities.timestamp_to_human(pending_intervals[0][0])
        end_time = joule.utilities.timestamp_to_human(pending_intervals[-1][0])
        click.echo(
            f"Merging from {start_time} to {end_time} ({len(pending_intervals)} intervals)")
    for interval in pending_intervals:
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
