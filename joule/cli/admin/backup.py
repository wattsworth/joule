import click
import subprocess
import configparser
import dsnparse
import os
import tempfile
import json

from joule import errors


@click.command(name="backup")
@click.option("-c", "--config", help="main configuration file", default="/etc/joule/main.conf")
@click.option("-f", "--file", help="backup file name", default="joule_backup.tar")
def admin_backup(config, file):
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

    if not file.endswith("tar"):
        file += ".tar"

    if os.path.isfile(file):
        raise click.ClickException("file [%s] already exists" % file)

    click.echo("Writing database to [%s]" % file)
    with tempfile.TemporaryDirectory(dir="./") as backup_path:

        # parse the dsn string
        parts = dsnparse.parse(config.database)

        # backup the database
        args = ["--format", "tar"]
        args += ["--checkpoint", "fast"]
        args += ["--pgdata", backup_path]
        args += ["--wal-method", "stream"]
        args += ["--progress"]
        args += ["--host", parts.host]
        args += ["--port", "%s" % parts.port]
        args += ["--username", parts.user]
        args += ["--label", "joule_backup"]
        cmd = ["pg_basebackup"] + args
        pg_proc_env = os.environ.copy()
        pg_proc_env["PGPASSWORD"] = parts.password
        subprocess.call(cmd, env=pg_proc_env)

        # add the database name and user
        db_info = {
            "database": parts.database,
            "user": parts.user,
            "password": parts.secret
        }
        with open(os.path.join(backup_path, "info.json"), 'w') as f:
            f.write(json.dumps(db_info, indent=2))

        # allow read access to wal
        os.chmod(os.path.join(backup_path, "pg_wal.tar"), 0o644)
        # combine backup into a single archive
        args = ["--append"]
        args += ["--directory", backup_path]
        args += ["--file", os.path.join(backup_path, "base.tar")]
        args += ["--remove-files"]
        args += ["pg_wal.tar"]
        args += ["info.json"]
        cmd = ["tar"] + args
        subprocess.call(cmd)

        # rename the tarball and move it
        os.rename(os.path.join(backup_path, "base.tar"), file)
        # remove the temporary directory
    click.echo("OK")
