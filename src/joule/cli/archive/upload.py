import click
import asyncio
from typing import List
from joule import errors
import os
import json
from joule.cli.config import Config, pass_config
from joule.utilities import archive_tools

@click.command(name="inspect")
@click.option('-f', "--flush", help="remove archives after successful upload", is_flag=True)
@click.argument("path",type=click.Path(exists=True, dir_okay=True))
@pass_config
def archive_upload(config: Config, flush:bool, path: str):
    """Upload archive(s) to a Joule node"""
    if os.path.isdir(path):
        archives = _find_joule_archives(path)
        if len(archives)==0:
            raise click.ClickException("no Joule archives found in this directory")
    elif os.path.isfile(path):            
        try:
            archive_tools.read_metadata(path)
        except ValueError:
            raise click.ClickException("this file does not look like a Joule archive")
        archives = [path]
    else:
        raise click.ClickException("invalid file")
    asyncio.run(_upload_archives(archives, config.node, flush))
    

def _find_joule_archives(path: str)->List[str]:
    #https://stackoverflow.com/questions/3207219
    if not os.path.isdir(path):
        raise click.ClickException("specify a directory")
    filenames = next(os.walk(path), (None, None, []))[2]
    file_paths = [os.path.join(path,name) for name in filenames]
    archives = []
    for file_path in file_paths:
        try:
            archive_tools.read_metadata(file_path)
            archives.append(file_path)
        except ValueError:
            pass # not a Joule archive
    return archives

async def _upload_archives(archives, node, flush):
    print("Uploading...")
    if len(archives)==1:
        logger = await node.archive_upload(archives[0])
        _print_messages(logger)        
        if flush:
            os.remove(archives[0])
        print("OK")
    else:
        with click.progressbar(archives) as bar:
            for archive in bar:
                logger = await node.archive_upload(archive)
                _print_messages(logger)
                if flush:
                    os.remove(archive)
    await node.close()
    print("Uploaded the following archive(s):")
    for archive in archives:
        print("\t"+archive)

def _print_messages(logger:archive_tools.ImportLogger):
    # TODO: make this look nicer
    click.echo(json.dumps(logger.to_json(),indent=2))