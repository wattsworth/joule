import os
import configparser
import asyncio
import logging
import time
import argparse
import signal
from aiohttp import web
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from typing import List

from joule.models import (Base, Worker, Supervisor, config, ConfigurationError,
                          SubscriptionError, DataStore, Stream)
from joule.models import NilmdbStore
from joule.services import (load_modules, load_streams)
import joule.controllers

log = logging.getLogger('joule')
Loop = asyncio.AbstractEventLoop


class Daemon(object):

    def __init__(self, my_config: config.JouleConfig):
        self.config: config.JouleConfig = my_config
        self.db: Session = None
        self.supervisor: Supervisor = None
        self.data_store: DataStore = None
        self.tasks: List[asyncio.Task] = []
        self.stop_requested = False

    def initialize(self, loop: Loop):
        # initialize the data store
        if self.config.data_store.store_type == config.DATASTORE.NILMDB:
            self.data_store: DataStore = \
                NilmdbStore(self.config.data_store.url,
                            self.config.data_store.insert_period,
                            self.config.data_store.cleanup_period, loop)
        else:
            log.error("Unsupported data store: " + self.config.data_store.type.value)
            exit(1)

        # connect to the database
        engine = create_engine('sqlite://')
        Base.metadata.create_all(engine)
        self.db = Session(bind=engine)

        # load modules and streams from configs
        load_streams.run(self.config.stream_directory, self.db)
        modules = load_modules.run(self.config.module_directory, self.db)

        # configure workers
        pending_workers = [Worker(m) for m in modules]
        registered_workers = []
        while len(pending_workers) > 0:
            for worker in pending_workers:
                if worker.subscribe_to_inputs(registered_workers, loop):
                    pending_workers.remove(worker)
                    registered_workers.append(worker)
                    break
            else:
                for w in pending_workers:
                    log.warning("[%s] is missing inputs" % w.module)
        self.supervisor = Supervisor(registered_workers)

    async def run(self, loop: Loop):
        # initialize streams in the data store
        await self.data_store.initialize(self.db.query(Stream).all())
        # start the supervisor (runs the workers)
        self.supervisor.start(loop)
        # start inserters by subscribing to the streams
        inserter_task_grp = self._spawn_inserters(loop)

        # start the API server
        app = web.Application()
        app['supervisor'] = self.supervisor
        app['data_store'] = self.data_store
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
        await runner.cleanup()
        self.db.close()

    def stop(self):
        self.stop_requested = True

    def _spawn_inserters(self, loop: Loop) -> asyncio.Task:
        inserter_tasks = []
        for stream in self.db.query(Stream).filter(Stream.keep_us != Stream.KEEP_NONE):
            try:
                subscription = self.supervisor.subscribe(stream, loop)
                task = self.data_store.spawn_inserter(stream,
                                                      subscription.queue,
                                                      loop)
                inserter_tasks.append(task)
            except SubscriptionError as e:
                logging.warning(e)
        return asyncio.gather(*inserter_tasks, loop=loop)


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
        my_config = config.build(custom_values=parser)
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
