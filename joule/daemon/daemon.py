

import os
import configparser
import asyncio
import logging
import time
import argparse
import signal
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from joule.models import (Base, Module, Worker, Supervisor)
from joule.daemon import (config)
from joule.services import (load_modules, load_streams)

log = logging.getLogger('joule')
Loop = asyncio.AbstractEventLoop


class Daemon(object):

    def __init__(self, my_config: config.JouleConfig, loop: Loop):
        self.config = my_config
        self.loop = loop
        self.db: Session = None
        self.supervisor = None
        
    def initialize(self):
        engine = create_engine('sqlite://')
        Base.metadata.create_all(engine)
        self.db = Session(bind=engine)
        load_streams.run(self.config.stream_directory, self.db)
        modules = load_modules.run(self.config.module_directory, self.db)

        pending_workers = [Worker(m) for m in modules]
        registered_workers = []
        while len(pending_workers) > 0:
            for worker in pending_workers:
                if worker.subscribe_to_inputs(registered_workers, self.loop):
                    pending_workers.remove(worker)
                    break
            else:
                for w in pending_workers:
                    log.warning("[%s] is missing inputs" % w.module)
        self.supervisor = Supervisor(registered_workers)

    async def run(self):
        await self.supervisor.run()


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
            raise errors.InvalidConfiguration("cannot load file [%s]" % args.config)
    parser = configparser.ConfigParser()
    parser.read(args.config)
    my_config = config.build(custom_values=parser)

    loop = asyncio.get_event_loop()
    loop.set_debug(True)
    daemon = Daemon(my_config, loop)
    daemon.initialize()
    loop.add_signal_handler(signal.SIGINT, daemon.stop)
    loop.run_until_complete(daemon.run())
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
            if now-prev < self.max_gap:
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

