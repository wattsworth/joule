import click
import requests
from tabulate import tabulate
import datetime
from typing import Dict

from joule.cmds.config import pass_config
from joule.models import stream, StreamInfo


@click.command(name="info")
@click.argument("path")
@pass_config
def stream_info(config, path):
    payload = {'path': path}
    json = _get(config.url + "/stream.json", params=payload)
    my_stream: stream.Stream = stream.from_json(json["stream"])
    # display stream information
    click.echo()
    click.echo("\tName:         %s" % my_stream.name)
    click.echo("\tDescription:  %s" % _optional_field(my_stream.description))
    click.echo("\tDatatype:     %s" % my_stream.datatype.name.lower())
    click.echo("\tKeep:         %s" % _display_keep(my_stream.keep_us))
    click.echo()
    # display information from the data store
    my_info: StreamInfo = StreamInfo(**json["data-info"])
    click.echo("\tStart:        %s" % _display_time(my_info.start))
    click.echo("\tEnd:          %s" % _display_time(my_info.end))
    click.echo("\tRows:         %d" % my_info.rows)
    click.echo()
    # display element information
    elem_data = []
    for element in my_stream.elements:
        elem_data.append([element.name,
                          _optional_field(element.units),
                          element.display_type.name.lower(),
                          _display_bounds(element.default_min,
                                          element.default_max)
                          ])
    # display element information
    click.echo(tabulate(elem_data, headers=["Name", "Units", "Display", "Min,Max"],
                        stralign="center",
                        tablefmt="fancy_grid"))


def _display_keep(keep: int) -> str:
    if keep == stream.Stream.KEEP_NONE:
        return "no data"
    if keep == stream.Stream.KEEP_ALL:
        return "all data"
    return str(datetime.timedelta(microseconds=keep))


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


def _get(url: str, params=None) -> Dict:
    resp = None  # to appease type checker
    try:
        resp = requests.get(url, params=params)
    except requests.ConnectionError:
        print("Error contacting Joule server at [%s]" % url)
        exit(1)
    if resp.status_code != 200:
        print("Error [%d]: %s" % (resp.status_code, resp.text))
        exit(1)
    return resp.json()