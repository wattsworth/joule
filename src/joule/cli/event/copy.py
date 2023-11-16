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
@click.option('-a', '--action', help="action to take if events already exist in the destination",
              type=click.Choice(['skip', 'ignore', 'replace', 'prompt']), default='prompt')
@click.option('-n', '--new', help="copy starts at the last timestamp of the destination", is_flag=True)
@click.option('-d', '--destination-node', help="node name or Nilmdb URL")
@click.argument("source")
@click.argument("destination")
@pass_config
def cli_copy(config: Config, start, end, action, new, destination_node, source, destination):
    """Copy events to a different stream."""
    try:
        if destination_node is None:
            dest_node = config.node
        else:
            dest_node = get_node(destination_node)
    except errors.ApiError:
        raise click.ClickException(f"Invalid destination node [{destination_node}]")
    try:
        replace_action = asyncio.run(_verify_action(dest_node, destination, action, start, end))
        asyncio.run(_run(config.node, dest_node, start, end, new, action, source, destination))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        asyncio.run(config.close_node())
        if destination_node is not None:  # different destination node
            asyncio.run(dest_node.close())
    click.echo("OK")


async def _replace_destination_events(node, stream, action, start, end):
    if action == 'replace':
        return True
    elif action == 'ignore':
        return False
    elif action == 'prompt':
        if await has_existing_events(node, stream, start, end):
            print(""""
                   There are already events in this destination, select how you want to procede:
                   [c]ancel: stop, do not copy anything
                   [i]gnore: ignore existing destination events, add source events. This may result in duplicate events
                   [r]eplace: remove all destination events, then add source events. This may result in data loss
                   Select an option (c,i or r): """)
            choice = click.getchar()
            if choice == 'c':
                raise click.ClickException("Action cancelled")
            elif action == 'i':
                print("\t ignoring existing events, running copy anyway")
                return False
            elif action == 'r':
                print("\t removing events in destination before running copy")
                return True

    else:
        raise click.ClickException("\t invalid option, cancelling copy")


async def has_existing_events(node, stream, start, end):
    try:
        count = await node.event_stream_count(stream, start=start, end=end)
        return count > 0
    except joule.errors.ApiError as e:
        if "does not exist" in str(e):
            return False
        else:
            raise e


async def _run(source_node, dest_node, start, end, new, replace, source, destination):
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
    # name = destination.split('/')[-1]
    # path = "/".join(destination.split('/')[:-1])
    source_stream = await source_node.event_stream_get(source)

    await dest_node.event_stream_get(destination, create=True,
                                     description=source_stream.description,
                                     event_fields=source_stream.event_fields,
                                     chunk_duration_us=source_stream.chunk_duration_us)
    if new:
        dest_info = await dest_node.event_stream_info(destination)
        start = dest_info.start_time
        print(f"Starting copy at {ts2h(start)}")
    # try:
    #    event_stream = joule.api.EventStream(name=name)
    #    await dest_node.event_stream_create(event_stream, path)
    # except joule.errors.ApiError:
    #    pass  # stream already exists
    if new:
        dest_info = await dest_node.event_stream_info(destination)
        start = dest_info.end
        if start is not None:
            print(f"Starting copy at {ts2h(dest_info.end)}")
    elif replace:
        print(f"Removing existing events from destination...", end="")
        await dest_node.event_stream_remove(destination, start, end)
        print("[OK]")

    stream_info = await source_node.event_stream_info(source)
    event_count = stream_info.event_count
    num_copied_events = 0
    with click.progressbar(length=event_count) as bar:
        # seen_event_ids = set()
        while True:
            events = await source_node.event_stream_read(source, start=start, end=end,
                                                         limit=1000, include_on_going_events=False)

            if len(events) == 0:
                break
            # new_events = []
            # for event in events:
            #    if event.id not in seen_event_ids:
            #        seen_event_ids.add(event.id)
            #        event.id = None  # remove the event id's so it inserts as a new event
            #        new_events.append(event)

            # if len(new_events) == 0:
            #    break

            await dest_node.event_stream_write(destination, events)
            num_copied_events += len(events)
            bar.update(len(events))
            start = events[-1].start_time + 1
        # bring bar up to 100%
        bar.update(event_count - num_copied_events)
