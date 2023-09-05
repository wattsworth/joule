import click
import asyncio

import joule.api
from joule.utilities import timestamp_to_human as ts2h
from joule.utilities import human_to_timestamp as h2ts
from joule import errors
from joule.api import get_node
from joule.cli.config import Config, pass_config


@click.command(name="copy")
@click.option('-s', "--start", help="timestamp or descriptive string")
@click.option('-e', "--end", help="timestamp or descriptive string")
@click.option('-r', "--replace", help="remove existing events in destination", is_flag=True)
@click.option('-n', '--new', help="copy starts at the last timestamp of the destination", is_flag=True)
@click.option('-d', '--destination-node', help="node name or Nilmdb URL")
@click.argument("source")
@click.argument("destination")
@pass_config
def cli_copy(config: Config, start, end, replace, new, destination_node, source, destination):
    """Copy events to a different stream."""
    try:
        if destination_node is None:
            dest_node = config.node
        else:
            dest_node = get_node(destination_node)
    except errors.ApiError:
        raise click.ClickException(f"Invalid destination node [{destination_node}]")
    try:
        asyncio.run(_run(config.node, dest_node, start, end, new, replace, source, destination))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        asyncio.run(config.close_node())
        if destination_node is not None:  # different destination node
            asyncio.run(dest_node.close())
    click.echo("OK")


async def _run(source_node,  dest_node, start, end, new, replace, source, destination):
    # make sure the time bounds make sense
    if start is not None:
        try:
            start = h2ts(start)
        except ValueError:
            raise errors.ApiError("invalid start time: [%s]" % start)
    if end is not None:
        try:
            end = h2ts(end)
        except ValueError:
            raise errors.ApiError("invalid end time: [%s]" % end)
    if (start is not None) and (end is not None) and ((end - start) <= 0):
        raise click.ClickException(f"Error: start {ts2h(start)} " +
                                   f"must be before end f{ts2h(end)}")

    # create the destination stream if necessary
    name = destination.split('/')[-1]
    path = "/".join(destination.split('/')[:-1])
    try:
        event_stream = joule.api.EventStream(name=name)
        await dest_node.event_stream_create(event_stream, path)
    except joule.errors.ApiError:
        pass  # stream already exists

    if replace:
        await dest_node.event_stream_remove(destination, start, end)

    stream_info = await source_node.event_stream_info(source)
    event_count = stream_info.event_count
    num_copied_events = 0
    with click.progressbar(length=event_count) as bar:
        seen_event_ids = set()
        while True:
            events = await source_node.event_stream_read(source, start=start, end=end,
                                                         limit=1000)

            new_events = []
            for event in events:
                if event.id not in seen_event_ids:
                    seen_event_ids.add(event.id)
                    event.id = None # remove the event id's so it inserts as a new event
                    new_events.append(event)

            if len(new_events) == 0:
                break

            await dest_node.event_stream_write(destination, new_events)
            num_copied_events += len(new_events)
            bar.update(len(new_events))
            start = new_events[-1].start_time + 1
        # bring bar up to 100%
        bar.update(event_count-num_copied_events)
