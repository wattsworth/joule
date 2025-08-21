import click
import asyncio

from joule import errors
from joule.cli.config import Config, pass_config
from joule.utilities import timestamp_to_human, human_to_timestamp


@click.command(name="inspect")
@click.option('-v', "--verbose", help="display more information")
@click.option('-d', "--directory", help="upload all archives in the directory")
@click.argument("path")
@pass_config
def archive_upload(config: Config, path: str):
    """Upload archive(s) to a Joule node"""
    print(f"Uploading {path}")