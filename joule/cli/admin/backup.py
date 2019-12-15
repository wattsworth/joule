import click
import subprocess
import configparser
import dsnparse
import os
import json
import asyncio
import shutil
from datetime import datetime
from joule import errors
import aiohttp


@click.command(name="backup")
@click.option("-c", "--config", help="main configuration file", default="/etc/joule/main.conf")
@click.option("-f", "--folder", help="backup folder name", default="joule_backup_NODE_DATE")
def admin_backup(config, folder):
    # expensive imports so only execute if the function is called
    from joule.services import load_config

    parser = configparser.ConfigParser()

    # load the Joule configuration file
    try:
        with open(config, 'r') as f:
            parser.read_file(f, config)
            config = load_config.run(custom_values=parser)
    except FileNotFoundError:
        raise click.ClickException("Cannot load joule configuration file at [%s]" % config)
    except PermissionError:
        raise click.ClickException("Cannot read joule configuration file at [%s] (run as root)" % config)
    except errors.ConfigurationError as e:
        raise click.ClickException("Invalid configuration: %s" % e)

    # demote priveleges
    if "SUDO_GID" in os.environ:
        os.setgid(int(os.environ["SUDO_GID"]))
    if "SUDO_UID" in os.environ:
        os.setuid(int(os.environ["SUDO_UID"]))

    if folder == "joule_backup_NODE_DATE":
        folder = "joule_backup_%s_%s" % (config.name, datetime.now().strftime("%Y%m%d_%H%M"))

    if os.path.exists(folder):
        raise click.ClickException("Requested folder [%s] already exists" % folder)

    os.mkdir(folder)

    # parse the dsn string
    parts = dsnparse.parse(config.database)

    # backup the database
    args = ["--format", "plain"]
    args += ["--checkpoint", "fast"]
    args += ["--pgdata", folder]
    args += ["--wal-method", "stream"]
    args += ["--progress"]
    args += ["--host", parts.host]
    args += ["--port", "%s" % parts.port]
    args += ["--username", parts.user]
    args += ["--label", "joule_backup"]
    cmd = ["pg_basebackup"] + args
    pg_proc_env = os.environ.copy()
    pg_proc_env["PGPASSWORD"] = parts.password
    click.echo("Copying up postgres database...")
    subprocess.call(cmd, env=pg_proc_env)

    # add the database name and user
    db_info = {
        "database": parts.database,
        "user": parts.user,
        "password": parts.secret,
        "nilmdb": config.nilmdb_url is not None
    }
    with open(os.path.join(folder, "info.json"), 'w') as f:
        f.write(json.dumps(db_info, indent=2))

    if config.nilmdb_url is None:
        click.echo("OK")
        return

    click.echo("Copying nilmdb database...")
    # retrieve the nilmdb data folder
    loop = asyncio.get_event_loop()
    nilmdb_folder = loop.run_until_complete(get_nilmdb_dir(config.nilmdb_url))
    nilmdb_backup = os.path.join(folder, "nilmdb")
    shutil.copytree(nilmdb_folder, nilmdb_backup, ignore=print_progress)
    click.echo("\nOK")


def print_progress(dir, contents):
    print('.', end="")
    return []


async def get_nilmdb_dir(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url + "/dbinfo") as resp:
            data = await resp.json()
            return data['path']
