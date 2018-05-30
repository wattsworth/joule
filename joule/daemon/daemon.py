

import os
import configparser
import asyncio
import json
import sqlite3
from .worker import Worker
from .errors import DaemonError
from . import stream, module

from joule.procdb import client as procdb_client
import logging
import functools
import argparse
import signal
from joule.utils import config_manager, nilmdb, time
from . import inserter, server, api

log = logging.getLogger('joule')


class Daemon(object):

    def __init__(self, config: JouleConfig):
        self.config = config
        
    def initialize(self, config):
        self.engine = create_engine('sqlite://')
        Base.metadata.create_all(engine)
        self.db = Session(bind=engine)
        self.streams = configure_streams.run(config.stream_dir, self.db)
        self.modules = configure_modules.run(config.module_dir, self.db)
        self.db.commit()

    def run(self, loop):
        """start each module and store runtime structures in a worker"""
        # only call this function once, error if called twice
        assert(len(self.workers) == 0)
        tasks = []
        runtime_tasks = []
        
        # loop through modules until they are all registered and started
        # if a module's inputs have no matching outputs, it can't run

        pending_workers = [Worker(m, procdb_client=self.procdb)
                           for m in self.modules]
        while(len(pending_workers) > 0):
            started_a_worker = False
            for w in pending_workers:
                if(w.register_inputs(self.path_workers)):
                    tasks.append(self._start_worker(w, loop=loop))
                    pending_workers.remove(w)
                    started_a_worker = True
            if(started_a_worker is False):
                for w in pending_workers:
                    logging.warning("Could not start %s because nobody is producing its inputs" %
                                    w.module)
                break

        tasks.append(asyncio.ensure_future(self._db_committer()))
        tasks += self._start_inserters(loop)

        # Factory function to allow the server to build inserters
        # returns an inserter and unsubscribe function
        async def inserter_factory(stream, time_range):
            self._validate_stream(stream)
            
            if(stream.path in self.write_locked_streams):
                raise Exception("[%s] is in use by another module " % stream.path)

            self.write_locked_streams.append(stream.path)

            if(time_range is not None):
                #remove time_range data
                await self.async_nilmdb_client.\
                          stream_auto_remove(stream.path,
                                             time_range[0],
                                             time_range[1])
            return (
                inserter.NilmDbInserter(
                    self.async_nilmdb_client,
                    stream.path,
                    insertion_period=self.NILMDB_INSERTION_PERIOD,
                    cleanup_period=self.NILMDB_CLEANUP_PERIOD,
                    keep_us=stream.keep_us,
                    decimate=stream.decimate),
                lambda: self.write_locked_streams.remove(stream.path)
            )       
        
        # Factory function to allow the server to subscribe to queues
        def subscription_factory(path, time_range):
            nonlocal runtime_tasks
            
            if(time_range is None):
                if path in self.path_workers:
                    (q, unsubscribe) = self.path_workers[path]()
                    return (self.path_streams[path].layout, q, unsubscribe)
                else:
                    raise Exception("path [%s] is unavailable" % path)
            else:
                # Run in historical isolation mode
                q = asyncio.Queue()
                info = self.nilmdb_client.stream_info(path)
                coro = self.async_nilmdb_client.\
                  stream_extract(q, path,
                                 info.layout,
                                 time_range[0],
                                 time_range[1])
                task = asyncio.ensure_future(coro)
                runtime_tasks.append(task)
                return (info.layout, q,
                        lambda: task.cancel())
            
        # add the stream server to the event loop
        coro = server.build_server(
            self.SERVER_IP_ADDRESS,
            self.SERVER_PORT,
            subscription_factory,
            inserter_factory, loop)

        my_server = loop.run_until_complete(coro)

        # add the API server to the event loop
        my_api = api.build_server(loop, '0.0.0.0', port=8080,
                                  nilmdb_url=self.NILMDB_URL,
                                  modules=self.modules)
        
        # commit records to database
        self.procdb.commit()

        # run joule
        loop.run_until_complete(asyncio.gather(*tasks))

        # clean up runtime tasks
        try:
            loop.run_until_complete(asyncio.gather(*runtime_tasks))
        except Exception:
            pass

        # shut down the servers
        loop.run_until_complete(my_api.shutdown())
        loop.run_until_complete(my_api.cleanup())
        my_server.close()

        loop.run_until_complete(my_server.wait_closed())

        # shut down the nilmdb connection
        if(self.async_nilmdb_client is not None):
            self.async_nilmdb_client.close()

    def stop(self):
        loop = asyncio.get_event_loop()
        self.stop_requested = True
        for worker in self.workers:
            asyncio.ensure_future(worker.stop(loop))
        for my_inserter in self.inserters:
            my_inserter.stop()

    def _start_inserters(self, loop):
        inserter_tasks = []
        for path in self.path_workers:
            stream = self.path_streams[path]
            # build inserters for any paths that have non-zero keeps
            if(stream.keep_us):
                my_inserter = inserter.NilmDbInserter(
                    self.async_nilmdb_client,
                    path,
                    insertion_period=self.NILMDB_INSERTION_PERIOD,
                    cleanup_period=self.NILMDB_CLEANUP_PERIOD,
                    keep_us=stream.keep_us,
                    decimate=stream.decimate)
                (q, _) = self.path_workers[path]()
                coro = my_inserter.process(q, loop=loop)
                task = asyncio.ensure_future(coro)
                self.inserters.append(my_inserter)
                inserter_tasks.append(task)
        return inserter_tasks

    def _start_worker(self, worker, loop):
        self.workers.append(worker)
        module = worker.module
        for path in module.output_paths.values():
            self.path_workers[path] = functools.partial(worker.subscribe, path)
        # waits here while worker runs
        return asyncio.ensure_future(worker.run())

    async def _db_committer(self, loop=None):
        while(not self.stop_requested):
            await asyncio.sleep(self.procdb_commit_interval)
            self.procdb.commit()


def load_configs(config_file):
    configs = {}
    if(config_file is not None):
        if(os.path.isfile(config_file) is False):
            raise config_manager.\
                InvalidConfiguration("cannot load file [%s]" % config_file)
        configs = configparser.ConfigParser()
        configs.read(config_file)
    return config_manager.load_configs(configs=configs)


def main(argv=None):
    parser = argparse.ArgumentParser("Joule Daemon")
    parser.add_argument("--config", default="/etc/joule/main.conf")
    args = parser.parse_args(argv)
    daemon = Daemon()
    log.addFilter(LogDedupFilter())
    logging.basicConfig(
        format='%(asctime)s %(levelname)s:%(message)s',
        level=logging.WARNING)
    try:
        configs = load_configs(args.config)
    except Exception as e:
        logging.error("Error loading configs: %s" % str(e))
        exit(1)
    try:
        daemon.initialize(configs)
    except DaemonError as e:
        logging.error("Error starting jouled [%s]" % str(e))
        exit(1)

    loop = asyncio.get_event_loop()
    loop.set_debug(True)
    loop.add_signal_handler(signal.SIGINT, daemon.stop)
    daemon.run(loop)
    loop.close()
    exit(0)


class LogDedupFilter:
    def __init__(self, name='', max_gap=5):
        self.max_gap = max_gap
        self.first_repeat = True
        self.last_time = 0
        self.last_msg = None

    def filter(self, record):
        if(self.last_msg is None):
            self.last_msg = record.msg
            return True
        if(self.last_msg == record.msg):
            # same log entry
            now = time.now()/1e6
            prev = self.last_time
            self.last_msg = record.msg
            self.last_time = now
            if(now-prev < self.max_gap):
                if(self.first_repeat):
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

