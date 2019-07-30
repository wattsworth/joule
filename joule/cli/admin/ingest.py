import click
import subprocess
import configparser
import json
import jinja2
import os
import tempfile
import time
import asyncio
import typing
import uuid
import sqlalchemy.exc
from tabulate import tabulate
from typing import Optional, List
import csv
from joule import utilities
from aiohttp.test_utils import unused_port
from joule import errors

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'local_postgres_templates')

if typing.TYPE_CHECKING:
    import sqlalchemy
    from sqlalchemy.orm import Session
    from joule.models import Base, Stream, folder, TimescaleStore


@click.command(name="ingest")
@click.option("-c", "--config", help="main configuration file", default="/etc/joule/main.conf")
@click.option("-f", "--file", help="backup file to restore", default="joule_backup.tar")
@click.option("-d", "--dsn", help="DSN connection string for live restore")
@click.option("-m", "--map", help="map file of source to destination streams")
@click.option("-b", "--pgctl-binary", help="override default pg_ctl location")
@click.option("-y", "--yes", help="do not ask for confirmation", is_flag=True)
@click.option('-s', "--start", help="timestamp or descriptive string")
@click.option('-e', "--end", help="timestamp or descriptive string")
def admin_ingest(config, file, dsn, map, pgctl_binary, yes, start, end):
    # expensive imports so only execute if the function is called
    from joule.services import load_config
    import sqlalchemy
    from sqlalchemy.orm import Session
    from joule.models import Base, TimescaleStore

    parser = configparser.ConfigParser()
    loop = asyncio.get_event_loop()

    # make sure the time bounds make sense
    if start is not None:
        try:
            start = utilities.human_to_timestamp(start)
        except ValueError:
            raise errors.ApiError("invalid start time: [%s]" % start)
    if end is not None:
        try:
            end = utilities.human_to_timestamp(end)
        except ValueError:
            raise errors.ApiError("invalid end time: [%s]" % end)
    if (start is not None) and (end is not None) and ((end - start) <= 0):
        raise click.ClickException("Error: start [%s] must be before end [%s]" % (
            utilities.timestamp_to_human(start),
            utilities.timestamp_to_human(end)))

    # parse the map file if specified
    stream_map = None
    if map is not None:
        stream_map = []
        try:
            with open(map, newline='') as csvfile:
                reader = csv.reader(csvfile, delimiter=',', quotechar='|', skipinitialspace=True)
                for row in reader:
                    if len(row) == 0:  # ignore blank lines
                        continue
                    if len(row) == 1 and len(row[0]) == 0: # line with only whitespace
                        continue
                    if row[0][0] == '#':  # ignore comments
                        continue
                    if len(row) != 2:
                        raise errors.ConfigurationError("""invalid map format. Refer to template below:
    
     # this line is a comment
     # only paths in this file will be copied
     # source and destination paths are separated by a ','
     
     /source/path, /destination/path
     /source/path2, /destination/path2
     #..etc
     
     """)
                    stream_map.append(row)
        except FileNotFoundError:
            raise click.ClickException("Cannot find map file at [%s]" % map)
        except PermissionError:
            raise click.ClickException("Cannot read map file at [%s]" % map)
        except errors.ConfigurationError as e:
            raise click.ClickException(str(e))

    # load the Joule configuration file
    try:
        with open(config, 'r') as f:
            parser.read_file(f, config)
            joule_config = load_config.run(custom_values=parser)
    except FileNotFoundError:
        raise click.ClickException("Cannot load joule configuration file at [%s]" % config)
    except PermissionError:
        raise click.ClickException("Cannot read joule configuration file at [%s] (run as root)" % config)
    except errors.ConfigurationError as e:
        raise click.ClickException("Invalid configuration: %s" % e)

    dest_engine = sqlalchemy.create_engine(joule_config.database)

    Base.metadata.create_all(dest_engine)
    dest_db = Session(bind=dest_engine)
    dest_datastore = TimescaleStore(joule_config.database, 0, 0, loop)

    # demote priveleges
    if "SUDO_GID" in os.environ:
        os.setgid(int(os.environ["SUDO_GID"]))
    if "SUDO_UID" in os.environ:
        os.setuid(int(os.environ["SUDO_UID"]))

    # create a log file for exec cmds
    pg_log_name = "joule_restore_log_%s.txt" % uuid.uuid4().hex.upper()[0:6]
    pg_log = open(pg_log_name, 'w')

    # if pgctl_binary is not specified, try to autodect it
    if pgctl_binary is None:
        try:
            completed_proc = subprocess.run(["psql", "-V"], stdout=subprocess.PIPE)
            output = completed_proc.stdout.decode('utf-8')
            version = output.split(" ")[2]
            major_version = version.split(".")[0]
            pgctl_binary = "/usr/lib/postgresql/%s/bin/pg_ctl" % major_version
        except (FileNotFoundError, IndexError):
            raise click.ClickException("cannot autodetect pg_ctl location, specify with -b")

    # determine if this is a file restore or live restore
    if dsn is not None:
        live_restore = True
        # to appease type checker
        backup_dir = None
        backup_path = ""
    else:
        if not os.path.isfile(file):
            raise click.ClickException("backup file [%s] does not exist" % file)
        backup_dir = tempfile.TemporaryDirectory(dir="./")
        backup_path = backup_dir.name
        dsn = start_postgres(file, backup_path, pgctl_binary, pg_log)
        live_restore = False

    src_engine = sqlalchemy.create_engine(dsn)

    num_tries = 0
    max_tries = 3
    while True:
        try:
            Base.metadata.create_all(src_engine)
            break
        except sqlalchemy.exc.OperationalError as e:
            if live_restore:
                raise click.ClickException(str(e))  # this should work immediately
            num_tries += 1
            click.echo("... attempting to connect to source database (%d/%d)" % (num_tries, max_tries))
            time.sleep(5)
            if num_tries >= max_tries:
                raise click.ClickException("cannot connect to source database, log saved in [%s]" % pg_log_name)

    src_db = Session(bind=src_engine)
    src_datastore = TimescaleStore(dsn, 0, 0, loop)

    try:
        loop.run_until_complete(run(src_db, dest_db,
                                    src_datastore, dest_datastore,
                                    stream_map, yes,
                                    start, end))
    except errors.ConfigurationError as e:
        print("Logs written to [%s]" % pg_log_name)
        raise click.ClickException(str(e))
    finally:
        # close connections
        dest_db.close()
        src_db.close()
        # clean up database if not a live_restore
        if not live_restore:
            args = ["-D", os.path.join(backup_path, "base")]
            args += ["stop"]
            cmd = [pgctl_binary] + args
            subprocess.call(cmd, stderr=pg_log, stdout=pg_log)
            # remove the database files
            backup_dir.cleanup()

    pg_log.close()
    os.remove(pg_log_name)


def start_postgres(archive, backup_path, pgctl_binary, log) -> str:
    # uncompress the archive
    click.echo("extracting database files")

    os.chmod(backup_path, 0o700)
    base_path = os.path.join(backup_path, "base")
    wal_path = os.path.join(backup_path, "wal")
    os.mkdir(base_path, mode=0o700)
    os.mkdir(wal_path, mode=0o700)

    # extract the base
    args = ["--extract"]
    args += ["--directory", base_path]
    args += ["--file", archive]
    cmd = ["tar"] + args
    subprocess.call(cmd)

    # extract the wal (and remove from base)
    args = ["--extract"]
    args += ["--directory", wal_path]
    args += ["--remove-files"]
    args += ["--file", os.path.join(base_path, 'pg_wal.tar')]
    cmd = ["tar"] + args
    subprocess.call(cmd, stderr=log)
    os.remove(os.path.join(base_path, "pg_wal.tar"))

    # read the info file for database name and user
    with open(os.path.join(backup_path, "base", "info.json"), 'r') as f:
        db_info = json.load(f)

    # create the config files
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATE_DIR))

    template = env.get_template("postgresql.conf.jinja2")
    sock_path = os.path.join(backup_path, "sock")
    os.mkdir(sock_path)
    db_port = unused_port()
    output = template.render(port=db_port, sock_dir=os.path.abspath(sock_path))
    with open(os.path.join(base_path, "postgresql.conf"), "w") as f:
        f.write(output)

    template = env.get_template("pg_hba.conf.jinja2")
    output = template.render(user=db_info["user"])
    with open(os.path.join(base_path, "pg_hba.conf"), "w") as f:
        f.write(output)

    template = env.get_template("pg_ident.conf.jinja2")
    output = template.render()
    with open(os.path.join(base_path, "pg_ident.conf"), "w") as f:
        f.write(output)

    template = env.get_template("recovery.conf.jinja2")
    output = template.render(wal_path=os.path.abspath(wal_path))
    with open(os.path.join(base_path, "recovery.conf"), "w") as f:
        f.write(output)

    # start postgres

    args = ["-D", base_path]
    args += ["start"]
    cmd = [pgctl_binary] + args
    try:
        subprocess.call(cmd, stderr=log, stdout=log)
    except FileNotFoundError:
        raise click.ClickException(
            "Cannot find pg_ctl, expected [%s] to exist. Specify location with -b" % pgctl_binary)

    click.echo("waiting for database to initialize")
    time.sleep(2)
    # connect to the database
    return "postgresql://%s:%s@localhost:%d/%s" % (
        db_info["user"],
        db_info["password"],
        db_port,
        db_info["database"])


async def run(src_db: 'Session',
              dest_db: 'Session',
              src_datastore: 'TimescaleStore',
              dest_datastore: 'TimescaleStore',
              stream_map: Optional[List],
              confirmed: bool,
              start: Optional[int],
              end: Optional[int]):
    from joule.models import Stream, folder, stream
    from joule.services import parse_pipe_config

    src_streams = src_db.query(Stream).all()
    dest_streams = dest_db.query(Stream).all()
    await src_datastore.initialize(src_streams)
    await dest_datastore.initialize(dest_streams)

    if stream_map is None:
        src_streams = src_db.query(Stream).all()
        src_paths = map(folder.get_stream_path, src_streams)
        stream_map = map(lambda _path: [_path, _path], src_paths)

    # create the copy map array
    copy_maps = []
    for item in stream_map:
        # get the source stream
        source = folder.find_stream_by_path(item[0], src_db)
        if source is None:
            raise errors.ConfigurationError("source stream [%s] does not exist" % item[0])
        src_intervals = await src_datastore.intervals(source, start, end)
        # get or create the destination stream
        dest = folder.find_stream_by_path(item[1], dest_db)
        if dest is None:
            (path, name, _) = parse_pipe_config.parse_pipe_config(item[1])
            dest_folder = folder.find(path, dest_db, create=True)
            dest = stream.from_json(source.to_json())
            # set the attributes on the new stream
            dest.name = name
            dest.keep_us = dest.KEEP_ALL
            dest.is_configured = False
            dest.is_source = False
            dest.is_destination = False
            dest.id = None
            for e in dest.elements:
                e.id = None
            dest_folder.streams.append(dest)
            dest_intervals = None
        else:
            # make sure the destination is compatible
            if dest.layout != source.layout:
                raise errors.ConfigurationError(
                    "source stream [%s] is not compatible with destination stream [%s]" % (item[0], item[1]))

            dest_intervals = await dest_datastore.intervals(dest, start, end)

        # figure out the time bounds to copy
        if dest_intervals is None:
            copy_intervals = src_intervals
        else:
            copy_intervals = utilities.interval_difference(src_intervals, dest_intervals)

        copy_maps.append(CopyMap(source, dest, copy_intervals))

    # display the copy table
    rows = []
    copy_required = False
    for item in copy_maps:
        if item.start is None:
            start = "\u2014"
            end = "\u2014"
        else:
            start = utilities.timestamp_to_human(item.start)
            end = utilities.timestamp_to_human(item.end)
            copy_required = True
        rows.append([item.source_path, item.dest_path, start, end])
    click.echo(tabulate(rows,
                        headers=["Source", "Destination", "From", "To"],
                        tablefmt="fancy_grid"))
    if not copy_required:
        click.echo("No data needs to be copied")
        return

    if not confirmed and not click.confirm("Start data copy?"):
        click.echo("cancelled")
        return

    dest_db.commit()
    # execute the copy
    for item in copy_maps:
        await copy(item, src_datastore, dest_datastore, src_db, dest_db)


async def copy(copy_map: 'CopyMap',
               src_datastore: 'TimescaleStore',
               dest_datastore: 'TimescaleStore',
               src_db: 'Session',
               dest_db: 'Session'):
    from joule.models import annotation, Annotation

    # compute the duration of data to copy
    duration = 0
    for interval in copy_map.intervals:
        duration += interval[1] - interval[0]

    with click.progressbar(
            label='[%s] --> [%s]' % (copy_map.source_path, copy_map.dest_path),
            length=duration) as bar:
        for interval in copy_map.intervals:
            await copy_interval(interval[0], interval[1] + 1, bar,
                                copy_map.source, copy_map.dest,
                                src_datastore, dest_datastore)
            start_dt = utilities.timestamp_to_datetime(interval[0])
            end_dt = utilities.timestamp_to_datetime(interval[1])
            # remove existing annotations (if any)
            dest_db.query(Annotation). \
                filter(Annotation.stream == copy_map.dest). \
                filter(Annotation.start >= start_dt). \
                filter(Annotation.start < end_dt). \
                delete()
            # retrieve source annotations that start in this interval
            items: List[Annotation] = src_db.query(Annotation). \
                filter(Annotation.stream == copy_map.source). \
                filter(Annotation.start >= start_dt). \
                filter(Annotation.start < end_dt)
            # copy them over to the destination
            for item in items:
                item_copy = annotation.from_json(item.to_json())
                item_copy.id = None
                item_copy.stream = copy_map.dest
                dest_db.add(item_copy)
            dest_db.commit()


async def copy_interval(start: int, end: int, bar,
                        src_stream: 'Stream', dest_stream: 'Stream',
                        src_datastore: 'TimescaleStore', dest_datastore: 'TimescaleStore'):
    from joule.models import pipes, Stream
    pipe = pipes.LocalPipe(src_stream.layout, write_limit=4)
    dest_stream.keep_us = Stream.KEEP_ALL  # do not delete any data
    insert_task = await dest_datastore.spawn_inserter(dest_stream,
                                                      pipe, asyncio.get_event_loop())

    last_ts = start

    async def writer(data, layout, decimated):
        nonlocal last_ts
        cur_ts = data['timestamp'][-1]
        await pipe.write(data)
        # await asyncio.sleep(0.01)
        bar.update(cur_ts - last_ts)
        last_ts = cur_ts

    await src_datastore.extract(src_stream, start, end, writer)
    await pipe.close()
    await insert_task

    bar.update(end - last_ts)


class CopyMap:
    def __init__(self, source: 'Stream', dest: 'Stream', intervals: List):
        self.source = source
        self.dest = dest
        self.intervals = intervals
        if len(intervals) > 0:
            self.start = intervals[0][0]
            self.end = intervals[-1][1]
        else:
            self.start = None
            self.end = None

    @property
    def source_path(self) -> str:
        from joule.models import folder
        if self.source is None:
            return "--none--"
        return folder.get_stream_path(self.source)

    @property
    def dest_path(self) -> str:
        from joule.models import folder
        if self.dest is None:
            return "--none--"
        return folder.get_stream_path(self.dest)

    def __str__(self):
        return "[%s] --> [%s] [%d intervals]" % (
            self.source_path,
            self.dest_path,
            len(self.intervals))
