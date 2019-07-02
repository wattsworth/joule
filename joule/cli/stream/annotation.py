import click
import asyncio
from tabulate import tabulate

from joule import errors
from joule.cli.config import pass_config
from joule.api import BaseNode
from joule import utilities


@click.command(name="annotations")
@click.argument("stream")
@click.option('-s', "--start", help="timestamp or descriptive string", default=None)
@click.option('-e', "--end", help="timestamp or descriptive string", default=None)
@click.option("-c", "--csv", is_flag=True, help="display in raw csv format")
@click.option("--delete", is_flag=True, help="remove annotations for this stream")
@pass_config
def cli_annotations(config, stream, start, end, delete, csv):
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(
            _run(config.node, stream, start, end, delete, csv))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        loop.run_until_complete(
            config.close_node())
        loop.close()


async def _run(node: BaseNode, stream, start, end, delete, csv):
    if start is not None:
        try:
            start = utilities.human_to_timestamp(start)
        except ValueError:
            raise click.ClickException("invalid start time: [%s]" % start)
    if end is not None:
        try:
            end = utilities.human_to_timestamp(end)
        except ValueError:
            raise click.ClickException("invalid end time: [%s]" % end)
    if delete:
        await node.stream_annotation_delete(stream, start, end)
        click.echo("OK")
        return
    annotations = await node.annotation_get(stream, start, end)
    if csv:
        print_csv(annotations)
    else:
        print_table(annotations)


def print_csv(annotations):
    for a in annotations:
        if a.end is not None:
            print("%s,%s,%d,%d" % (a.title, a.content, a.start, a.end))
        else:
            print("%s,%s,%d" % (a.title, a.content, a.start))


def print_table(annotations):
    headers = ["Title", "Content", "Start", "End"]
    result = []
    for a in annotations:
        row = [a.title, a.content, utilities.timestamp_to_human(a.start)]
        if a.end is not None:
            row.append(utilities.timestamp_to_human(a.end))
        else:
            row.append("\u2014")
        result.append(row)
    click.echo(tabulate(result,
                        headers=headers,
                        tablefmt="fancy_grid"))
