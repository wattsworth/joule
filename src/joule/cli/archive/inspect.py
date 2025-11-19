import click
from joule.cli.config import Config, pass_config
from joule.utilities import timestamp_to_human as ts2h
from joule.utilities import archive_tools

@click.command(name="inspect")
@click.option('-v', "--verbose", is_flag=True, help="display more information")
@click.argument("archive", type=click.Path(exists=True))
@pass_config
def archive_inspect(config: Config, archive: str, verbose):
    """Display the contents of an archive"""
    try:
        metadata = archive_tools.read_metadata(archive)
        print_info(metadata, verbose)
    except ValueError:
        raise click.ClickException(f"{archive} is not a valid joule archive")

def print_info(metadata, verbose):
    click.echo('========= Source ===========')
    click.echo(f'Node:\t{metadata["node"]}')
    click.echo(f'Label:\t{metadata["name"]}')
    click.echo(f'Date:\t{ts2h(metadata["created_at"])}')
    click.echo('')
    click.echo('========= Contents ========')
    start_times = [summary['start_ts'] for summary in metadata['data_streams']+metadata['event_streams'] if summary['end_ts'] is not None]
    end_times = [summary['end_ts'] for summary in metadata['data_streams']+metadata['event_streams'] if summary['end_ts'] is not None]
    if len(start_times)>0:
        click.echo(f'Start:\t{ts2h(min(start_times))}')
        click.echo(f'End:\t{ts2h(max(end_times))}')
        click.echo(f"{len(metadata['data_streams'])} data streams, {len(metadata['event_streams'])} event streams")
    else: 
        click.echo('--no stream data--\n')
        return
    if not verbose:
        return
    # veborse information
    for stream_data in metadata['data_streams']:
        click.echo('-------- Data Stream -------')
        click.echo(f'Label:     {stream_data["source_label"]}')
        click.echo(f'Path:      {stream_data["stream_path"]}')
        click.echo(f'Layout:    {stream_data["stream_layout"]}')
        click.echo(f'Rows:      {stream_data["row_count"]}')
        click.echo(f'Intervals: {stream_data["interval_count"]}')
    for stream_data in metadata['event_streams']:
        click.echo('-------- Event Stream ------')
        click.echo(f'Label:     {stream_data["source_label"]}')
        click.echo(f'Path:      {stream_data["stream_path"]}')
        click.echo(f'Events:    {stream_data["event_count"]}')
        fields = ','.join(stream_data["event_fields"].keys())
        if len(fields)==0:
            fields='--none--'
        click.echo(f'Fields:    {fields}')

    click.echo('')
