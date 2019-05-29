import click
import asyncio

from joule.cli.config import pass_config
from joule.api.data import data_delete
from joule.utilities import human_to_timestamp
from joule import errors


@click.command(name="delete")
@click.option("-s", "--start", "start", help="timestamp or descriptive string")
@click.option("-e", "--end", "end", help="timestamp or descriptive string")
@click.option("--all", is_flag=True, help="remove all data")
@click.argument("stream")
@pass_config
def data_remove(config, start, end, all, stream):
    loop = asyncio.get_event_loop()
    if all:
        if start is not None or end is not None:
            raise click.ClickException("specify either --all or --start/--end")
    if all is None and start is None and end is None:
        raise click.ClickException("specify either --all or --start/--end")
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
        loop.run_until_complete(config.node.data_delete(
            stream, start, end))
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    except:
        import traceback
        traceback.print_exc()
    finally:
        loop.run_until_complete(
            config.close_node())
        loop.close()
    click.echo("OK")
