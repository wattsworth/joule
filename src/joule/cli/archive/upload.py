import click
import asyncio
from typing import List
from joule import errors
import os
import json
from joule.cli.config import Config, pass_config
from joule.utilities import archive_tools

@click.command(name="upload")
@click.option('-f', "--flush", help="remove archives after successful upload", is_flag=True)
@click.option('-e', "--quit-on-error", help="quit upload on error", is_flag=True)
@click.option('-v', "--verbose", help="display info messages", is_flag=True)
@click.argument("path",type=click.Path(exists=True, dir_okay=True))
@pass_config
def archive_upload(config: Config, flush:bool, quit_on_error:bool, verbose:bool, path: str):
    """Upload archive(s) to a Joule node"""
    if os.path.isdir(path):
        archives = _find_joule_archives(path)
        if len(archives)==0:
            raise click.ClickException("no Joule archives found in this directory")
    else:       
        try:
            archive_tools.read_metadata(path)
        except ValueError:
            raise click.ClickException("this file does not look like a Joule archive")
        archives = [path]
    asyncio.run(_upload_archives(archives, config.node, flush, quit_on_error, verbose))
    

def _find_joule_archives(path: str)->List[str]:
    #https://stackoverflow.com/questions/3207219
    filenames = next(os.walk(path), (None, None, []))[2]
    file_paths = [os.path.join(path,name) for name in filenames]
    archives = []
    for file_path in file_paths:
        try:
            archive_tools.read_metadata(file_path)
            archives.append(file_path)
        except ValueError:
            pass # not a Joule archive
    archives.sort()
    return archives

async def _upload_archives(archives, node, flush, quit_on_error, verbose):
    print("\nUploading...")
    logs = {}
    if len(archives)==1:
        archive = archives[0] # only one archive, do not show progress bar
        logger = await node.archive_upload(archive)
        logs[archive] = logger
        if logger.success and flush:
            os.remove(archive)
        print("OK")
    else:
        with click.progressbar(archives) as bar:
            for archive in bar:
                logger = await node.archive_upload(archive)
                logs[archive] = logger
                if not logger.success and quit_on_error:
                    break
                # only flush the file if the upload was succesful
                if logger.success and flush:
                    os.remove(archive)
    await node.close()
    print("\nUploaded the following archive(s):\n")
    for archive, logger in logs.items():
        if logger.success:
            if verbose and logger.has_info:
                for msg in logger.info_messages:
                    click.echo(f"\t{msg}")
            else:
                click.echo(f"{archive}\t[OK]")
        else:
            click.echo(f"{archive}:")
            if logger.has_info and verbose:
                click.echo("\t=== INFO ===")
                for msg in logger.info_messages:
                    click.echo(f"\t{msg}")
            if logger.has_errors:
                click.echo("\t=== ERRORS ===")
                for msg in logger.error_messages:
                    click.echo(f"\t{msg}")
            if logger.has_warnings:
                click.echo("\t=== WARNINGS ===")
                for msg in logger.warning_messages:
                    click.echo(f"\t{msg}")

def _print_messages(logger:archive_tools.ImportLogger):
    # TODO: make this look nicer
    click.echo(json.dumps(logger.to_json(),indent=2))