import os
import configparser
import asyncio
import logging
import time
import argparse
import signal
from aiohttp import web
import faulthandler
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from typing import List

from joule.models import (Base, Worker, Supervisor, config,
                          DataStore, Stream, pipes)
from joule.errors import ConfigurationError, SubscriptionError
from joule.models import NilmdbStore, TimescaleStore
from joule.models.data_store.errors import DataError
from joule.services import (load_modules, load_streams, load_config, load_databases)
import joule.controllers

log = logging.getLogger('joule')
async_log = logging.getLogger('asyncio')
async_log.setLevel(logging.WARNING)
Loop = asyncio.AbstractEventLoop
faulthandler.enable()


class Daemon(object):

    def __init__(self, my_config: config.JouleConfig):
        self.config: config.JouleConfig = my_config
        self.db: Session = None
        self.supervisor: Supervisor = None
        self.data_store: DataStore = None
        self.tasks: List[asyncio.Task] = []
        self.stop_requested = False

    def initialize(self, loop: Loop):
        # load the database configs
        databases = load_databases.run(self.config.database_directory)

        # initialize the data store database
        db_name = self.config.data_store.database_name
        if db_name not in databases:
            log.error("Specified database [%s] is not configured" % db_name)
            exit(1)
        database = databases[db_name]
        if database.backend == config.BACKEND.NILMDB:
            self.data_store: DataStore = \
                NilmdbStore(database.url,
                            self.config.data_store.insert_period,
                            self.config.data_store.cleanup_period, loop)
        elif database.backend == config.BACKEND.TIMESCALE:
            self.data_store: DataStore = \
                TimescaleStore()
        else:
            log.error("Unsupported data store type: " + database.backend.value)
            exit(1)

        # connect to the metadata database
        db_name = self.config.database_name
        if db_name not in databases:
            log.error("Specified database [%s] is not configured" % db_name)
            exit(1)
        database = databases[db_name]
        engine = create_engine(database.engine_config)
        Base.metadata.create_all(engine)
        self.db = Session(bind=engine)

        # reset flags on streams, these will be set by load_modules and load_streams
        for stream in self.db.query(Stream).all():
            stream.is_configured = False
            stream.is_destination = False
            stream.is_source = False

        # load modules and streams from configs
        load_streams.run(self.config.stream_directory, self.db)
        modules = load_modules.run(self.config.module_directory, self.db)

        # configure workers
        workers = [Worker(m) for m in modules]
        self.supervisor = Supervisor(workers)

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
        app = web.Application()
        app['supervisor'] = self.supervisor
        app['data-store'] = self.data_store
        app['db'] = self.db
        app.add_routes(joule.controllers.routes)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.config.ip_address, self.config.port)
        await site.start()

        # sleep and check for stop condition
        while not self.stop_requested:
            await asyncio.sleep(0.5)

        # clean everything up
        await self.supervisor.stop(loop)
        inserter_task_grp.cancel()
        await inserter_task_grp
        self.data_store.close()
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
            pipe = pipes.LocalPipe(layout=stream.layout, loop=loop, name='inserter:%s'%stream.name)
            unsubscribe = self.supervisor.subscribe(stream, pipe, loop)
            try:
                await self.data_store.spawn_inserter(stream, pipe, loop)
                break  # inserter terminated, program is closing
            except DataError as e:
                msg = "stream [%s]: %s" % (stream.name, str(e))
                await self.supervisor.restart_producer(stream, loop, msg=msg)
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
    loop = asyncio.get_event_loop()
    loop.set_debug(True)
    daemon = Daemon(my_config)
    daemon.initialize(loop)
    loop.add_signal_handler(signal.SIGINT, daemon.stop)
    loop.run_until_complete(daemon.run(loop))
    loop.close()
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

if __name__=="__main__":
    main()