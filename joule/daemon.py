import os
import configparser
import asyncio
import logging
import time
import argparse
import uvloop
import signal
import secrets
from aiohttp import web
import faulthandler
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import List
import psutil
import dsnparse
import sys

from joule.models import (Base, Worker, config,
                          DataStore, Stream, pipes)
from joule.models.supervisor import Supervisor
from joule.errors import ConfigurationError, SubscriptionError
from joule.models import NilmdbStore, TimescaleStore, Follower
from joule.models.data_store.errors import DataError
from joule.api import TcpNode
from joule.services import (load_modules, load_streams, load_config)
import joule.middleware
import joule.controllers
from joule.utilities import ConnectionInfo
import ssl

log = logging.getLogger('joule')
async_log = logging.getLogger('asyncio')
async_log.setLevel(logging.WARNING)
Loop = asyncio.AbstractEventLoop
faulthandler.enable()

SQL_DIR = os.path.join(os.path.dirname(__file__), 'sql')

class Daemon(object):

    def __init__(self, my_config: config.JouleConfig):
        self.config: config.JouleConfig = my_config
        self.db: Session = None
        self.engine = None
        self.supervisor: Supervisor = None
        self.data_store: DataStore = None
        self.module_connection_info = None
        self.tasks: List[asyncio.Task] = []
        self.stop_requested = False

    def initialize(self, loop: Loop):

        # make sure this is the only copy of jouled running
        pid_file = os.path.join(self.config.socket_directory, 'pid')
        if os.path.exists(pid_file):
            with open(pid_file, 'r') as f:
                pid = int(f.readline())
                if psutil.pid_exists(pid):
                    log.error("jouled is already running with pid %d" % pid)
                    sys.exit(1)
        # clear out the socket directory
        for file_name in os.listdir(self.config.socket_directory):
            path = os.path.join(self.config.socket_directory, file_name)
            os.unlink(path)
        # write our pid
        with open(pid_file, 'w') as f:
            f.write('%d\n' % os.getpid())
        os.chmod(pid_file, 0o600)

        if self.config.nilmdb_url is not None:
            self.data_store: DataStore = \
                NilmdbStore(self.config.nilmdb_url,
                            self.config.insert_period,
                            self.config.cleanup_period, loop)
        else:
            self.data_store: DataStore = \
                TimescaleStore(self.config.database, self.config.insert_period,
                               self.config.cleanup_period, loop)

        engine = create_engine(self.config.database, echo=False)
        self.engine = engine  # keep for erasing database if needed

        # create a database user for modules
        password = secrets.token_hex(8)
        parsed_dsn = dsnparse.parse(self.config.database)
        self.module_connection_info = ConnectionInfo(username="joule_module",
                                                     password=password,
                                                     port=parsed_dsn.port,
                                                     host=parsed_dsn.host,
                                                     database=parsed_dsn.database)
        # NOTE: joule user must be able to create a role and grant access to db
        # ALTER ROLE joule WITH CREATEROLE;
        # GRANT ALL PRIVILEGES ON DATABASE joule TO joule WITH GRANT OPTION;
        with engine.connect() as conn:
            conn.execute('CREATE SCHEMA IF NOT EXISTS data')
            conn.execute('CREATE SCHEMA IF NOT EXISTS metadata')

            # create a module user
            cmd = """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'joule_module') THEN
                CREATE USER joule_module;
            END IF;
            END
            $$;"""
            conn.execute(cmd)
            conn.execute("ALTER ROLE joule_module WITH PASSWORD '%s'" % password)
            conn.execute("GRANT CONNECT ON DATABASE %s TO joule_module" % parsed_dsn.database)
            conn.execute("GRANT USAGE ON SCHEMA data TO joule_module")
            conn.execute("GRANT USAGE ON SCHEMA metadata TO joule_module")
            conn.execute("GRANT SELECT ON ALL TABLES IN SCHEMA metadata TO joule_module;")
            conn.execute("GRANT SELECT ON ALL TABLES IN SCHEMA data TO joule_module;")
            # test out pg_read_all_settings command
            conn.execute("show data_directory")
            # load custom functions
            for file in os.listdir(SQL_DIR):
                file_path = os.path.join(SQL_DIR, file)
                with open(file_path, 'r') as f:
                    conn.execute(text(f.read()))
            conn.execute("GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO joule_module;")
        Base.metadata.create_all(engine)
        self.db = Session(bind=engine)

        # reset flags on streams, these will be set by load_modules and load_streams
        for stream in self.db.query(Stream).all():
            stream.is_configured = False
            stream.is_destination = False
            stream.is_source = False

        # load modules, streams, and proxies, from configs
        load_streams.run(self.config.stream_directory, self.db)
        modules = load_modules.run(self.config.module_directory, self.db)

        # configure security parameters
        self.ssl_context = None
        self.cafile = ""
        if self.config.security is not None:
            self.ssl_context = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
            self.ssl_context.load_cert_chain(certfile=self.config.security.certfile,
                                             keyfile=self.config.security.keyfile)
            if self.config.security.cafile != "":
                # publish the cafile location to the environment for modules to use
                os.environ["JOULE_CA_FILE"] = self.config.security.cafile
                self.cafile = self.config.security.cafile
        # configure workers
        workers = [Worker(m) for m in modules]

        def get_node(name: str):
            follower = self.db.query(Follower) \
                .filter_by(name=name) \
                .one_or_none()
            if follower is None:
                return None

            return TcpNode(follower.name, follower.location,
                           follower.key,
                           self.cafile, loop)

        self.supervisor = Supervisor(workers, self.config.proxies, get_node)

        # save the metadata
        self.db.commit()

    async def run(self, loop: Loop):
        # initialize streams in the data store
        try:
            await self.data_store.initialize(self.db.query(Stream).all())
        except DataError as e:
            log.error("Database error: %s" % e)
            exit(1)
        # start the supervisor (runs the workers)
        await self.supervisor.start(loop)

        # start inserters by subscribing to the streams
        inserter_tasks = []
        for stream in self.db.query(Stream).filter(Stream.keep_us != Stream.KEEP_NONE):
            if not stream.is_destination:
                continue  # only subscribe to active streams
            try:
                task = self._spawn_inserter(stream, loop)
                inserter_tasks.append(task)
            except SubscriptionError as e:
                logging.warning(e)
        inserter_task_grp = asyncio.gather(*inserter_tasks, loop=loop)

        # start the API server
        middlewares = [
            joule.middleware.sql_rollback,
            joule.middleware.authorize(
                exemptions=joule.controllers.insecure_routes),
            ]
        app = web.Application(middlewares=middlewares)

        app['module-connection-info'] = self.module_connection_info
        app['supervisor'] = self.supervisor
        app['data-store'] = self.data_store
        app['db'] = self.db
        # used to tell master's this node's info

        # if the API is proxied the base_uri
        # will be retrieved from the X-Api-Base-Uri header
        app['base_uri'] = ""

        # if the API is proxied the port
        # will be retrieved from the X-Api-Port header
        app['name'] = self.config.name
        app['port'] = self.config.port

        # note, if the API is proxied the scheme
        # will be retrieved from the X-Api-Scheme header
        if self.ssl_context is None:
            app['scheme'] = 'http'
        else:
            app['scheme'] = 'https'

        # for acting as a client when accessing remote streams and joining other nodes
        app['cafile'] = self.cafile

        app.add_routes(joule.controllers.routes)
        runner = web.AppRunner(app)

        await runner.setup()
        if self.config.ip_address is not None:
            site = web.TCPSite(runner, self.config.ip_address,
                               self.config.port,
                               ssl_context=self.ssl_context)
            await site.start()

        sock_file = os.path.join(self.config.socket_directory, 'api')
        sock_site = web.UnixSite(runner, sock_file)
        await sock_site.start()
        os.chmod(sock_file, 0o600)

        # sleep and check for stop condition
        while not self.stop_requested:
            await asyncio.sleep(0.5)

        # clean everything up
        await self.supervisor.stop(loop)
        inserter_task_grp.cancel()
        try:
            await inserter_task_grp
        except asyncio.CancelledError:
            pass
        await self.data_store.close()
        try:
            await asyncio.wait_for(runner.shutdown(), 5)
            await asyncio.wait_for(runner.cleanup(), 5)
        except asyncio.TimeoutError:
            log.warning("unclean server shutdown, subscribed clients?")
        self.db.close()

    def stop(self):
        self.stop_requested = True

    async def _spawn_inserter(self, stream: Stream, loop: Loop):
        while True:
            pipe = pipes.LocalPipe(layout=stream.layout, loop=loop, name='inserter:%s' % stream.name)
            unsubscribe = self.supervisor.subscribe(stream, pipe, loop)
            task = None
            try:
                task = await self.data_store.spawn_inserter(stream, pipe, loop)
                await task
                break  # inserter terminated, program is closing
            except DataError as e:
                msg = "stream [%s]: %s" % (stream.name, str(e))
                await self.supervisor.restart_producer(stream, loop, msg=msg)
            except asyncio.CancelledError:
                if task is not None:
                    task.cancel()
                break
            unsubscribe()


def main(argv=None):
    parser = argparse.ArgumentParser("Joule Daemon")
    parser.add_argument("--config", default="/etc/joule/main.conf")
    args = parser.parse_args(argv)
    log.addFilter(LogDedupFilter())
    logging.basicConfig(
        format='%(asctime)s %(levelname)s:%(message)s',
        level=logging.WARNING)
    if args.config is not None:
        if os.path.isfile(args.config) is False:
            log.error("Invalid configuration: cannot load file [%s]" % args.config)
            exit(1)
    parser = configparser.ConfigParser()
    parser.read(args.config)
    my_config = None
    try:
        my_config = load_config.run(custom_values=parser)
    except ConfigurationError as e:
        log.error("Invalid configuration: %s" % e)
        exit(1)

    # uvloop uses libuv which does not support
    # connections to abstract namespace sockets
    # https://github.com/joyent/libuv/issues/1486

    #asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

    loop = asyncio.get_event_loop()
    loop.set_debug(True)
    daemon = Daemon(my_config)
    try:
        daemon.initialize(loop)
    except SQLAlchemyError as e:
        print("""
        Error initializing database, ensure user 'joule' has sufficient permissions:
        From a shell run
        $> sudo -u postgres psql
        postgres=# ALTER ROLE joule WITH CREATEROLE REPLICATION;
        postgres=# GRANT ALL PRIVILEGES ON DATABASE joule TO joule WITH GRANT OPTION;
        postgres=# GRANT pg_read_all_settings TO joule;
        """)
        loop.close()
        exit(1)

    loop.add_signal_handler(signal.SIGINT, daemon.stop)
    loop.add_signal_handler(signal.SIGTERM, daemon.stop)

    loop.run_until_complete(daemon.run(loop))
    loop.close()

    # clear out the socket directory
    for file_name in os.listdir(my_config.socket_directory):
        path = os.path.join(my_config.socket_directory, file_name)
        os.unlink(path)
    exit(0)


class LogDedupFilter:
    def __init__(self, name='', max_gap=5):
        self.max_gap = max_gap
        self.first_repeat = True
        self.last_time = 0
        self.last_msg = None

    def filter(self, record):
        if self.last_msg is None:
            self.last_msg = record.msg
            return True
        if self.last_msg == record.msg:
            # same log entry
            now = time.time()
            prev = self.last_time
            self.last_msg = record.msg
            self.last_time = now
            if now - prev < self.max_gap:
                if self.first_repeat:
                    record.msg = "[...repeats]"
                    self.first_repeat = False
                    return True
                else:
                    return False  # suppress
            return True  # far enough apart

        self.last_time = 0
        self.last_msg = record.msg
        self.first_repeat = True
        return True


if __name__ == "__main__":
    main()
