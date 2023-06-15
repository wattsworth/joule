import click
from tabulate import tabulate
import datetime
import asyncio

from joule.models import data_stream
from joule import errors
from joule.cli.config import pass_config


@click.command(name="info")
@click.option('-e', "--elements", help="show element information", is_flag=True)
@click.argument("path")
@pass_config
def cli_info(config, elements, path):
    """Display stream information."""
    try:
        asyncio.run(
            _run(config.node, path, elements))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        asyncio.run(
            config.close_node())


async def _run(node, path, show_elements):
    my_stream = await node.data_stream_get(path)
    # display stream information
    click.echo()
    click.echo("Data Stream Information:")
    click.echo("\tName:         %s" % my_stream.name)
    click.echo("\tDescription:  %s" % _optional_field(my_stream.description))
    click.echo("\tDatatype:     %s" % my_stream.datatype.lower())
    click.echo("\tKeep:         %s" % _display_keep(my_stream.keep_us))
    click.echo("\tDecimate:     %s" % _display_decimate(my_stream.decimate))
    click.echo()
    # display information from the data store
    click.echo("\tStatus:       %s" % _display_status(my_stream.locked, my_stream.active))
    my_info = await node.data_stream_info(path)
    click.echo("\tStart:        %s" % _display_time(my_info.start))
    click.echo("\tEnd:          %s" % _display_time(my_info.end))
    click.echo("\tRows:         %d" % my_info.rows)
    # display annotation information
    annotation_info = await node.annotation_info(path)
    click.echo("\tAnnotation:   %d" % annotation_info.count)
    click.echo()
    # display element information
    if show_elements:
        elem_data = []
        for element in my_stream.elements:
            elem_data.append([element.name,
                              _optional_field(element.units),
                              element.display_type.lower(),
                              _display_bounds(element.default_max,
                                              element.default_min)
                              ])
        # display element information
        click.echo(tabulate(elem_data, headers=["Name", "Units", "Display", "Min,Max"],
                            stralign="center",
                            tablefmt="fancy_grid"))


def _display_decimate(decimate: bool) -> str:
    if decimate:
        return "yes"
    else:
        return "no"


def _display_keep(keep: int) -> str:
    if keep == data_stream.DataStream.KEEP_NONE:
        return "no data"
    if keep == data_stream.DataStream.KEEP_ALL:
        return "all data"
    return str(datetime.timedelta(microseconds=keep))


def _display_status(locked: bool, active: bool) -> str:
    if active:
        return click.style("\u25CF ", fg="green") + "[active]"
    elif locked:
        return click.style("\u25CF ", fg="cyan") + "[configured]"
    else:
        return "[idle]"


def _display_time(time: int) -> str:
    if time is None:
        return u"\u2014"  # emdash
    return str(datetime.datetime.fromtimestamp(time/1e6))


def _display_bounds(max_: float, min_: float) -> str:
    if max_ is None and min_ is None:
        return "auto"
    elif max_ is None:
        return "%d,[auto]" % min_
    elif min_ is None:
        return "[auto],%d" % max_
    else:
        return "%d,%d" % (min_, max_)


def _optional_field(value: str) -> str:
    if value is None or value == "":
        return u"\u2014"  # emdash
    else:
        return value
