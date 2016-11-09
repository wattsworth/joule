

import os
import configparser
import asyncio
from .inputmodule import InputModule
from .worker import Worker
from .errors import DaemonError
from joule.procdb import client as procdb_client
import logging

import argparse
import nilmdb.client
import signal
from joule.utils import config_manager
from . import inserter

PROC_DB = "/tmp/joule-proc-db.sqlite"

class Daemon(object):
    log = logging.getLogger(__name__)
    
    def __init__(self):
        
        #populated by initialize
        self.procdb = None
        self.nilmdb_client = None
        self.stop_requested = False
        self.input_modules = []
        #runtime structures
        self.worked_paths = {}
        self.workers = []
        self.inserters = []
        
    def initialize(self,config):
        #Build a NilmDB client
        nilmdb_url = config.nilmdb.url
        self.nilmdb_client = nilmdb.client.numpyclient.\
                             NumpyClient(nilmdb_url)

        #Set up the ProcDB
        self.db_path = PROC_DB
        self.procdb = procdb_client.SQLClient(config.procdb.db_path,
                                              config.nilmdb.url)
        self.procdb.clear_input_modules()            
        
        #Set up the input modules
        module_dir = config.jouled.module_directory
        for module_config in os.listdir(module_dir):
            if(not module_config.endswith(".conf")):
                continue
            config_path = os.path.join(module_dir,module_config)
            self._build_module(config_path)

    def run(self,loop):
        """start each module and store runtime structures in a worker"""
        #only call this function once, error if called twice
        assert(len(self.workers)==0)
        tasks = []
        #set up module inputs

        #loop through modules until they are all registered and started
        #if a module cannot be registered log an error

        pending_workers = [Worker(m,procdb_client = self.procdb)
                           for m in self.input_modules]
        while(len(pending_workers)>0):
            started_a_worker = False
            for w in pending_workers:
                if(w.register_inputs(self.worked_paths)):
                    tasks.append(self._start_worker(w,loop=loop))
                    pending_workers.remove(w)
                    started_a_worker = True
            if(started_a_worker==False):
                for w in pending_workers:
                    logging.warn("Could not start [%s] because its inputs are not available"%
                                 w.module)
                break
            
        tasks.append(self._db_committer())

        loop.run_until_complete(asyncio.gather(*tasks))
                                

    def stop(self):
        loop = asyncio.get_event_loop()
        self.stop_requested=True
        for worker in self.workers:
            asyncio.ensure_future(worker.stop(loop))

        
    def _build_module(self,module_config):
        """ create an input module from config file
        """
        config = configparser.ConfigParser()
        config.read(module_config)
        module = InputModule()
        try:
            module.initialize(config)
            self.procdb.register_input_module(module,module_config)
        except (DaemonError, procdb_client.ConfigError) as e:
            self.log.error("Cannot load module [%s]: \n\t%s"%(module_config,e))
            return
        self.input_modules.append(module)

    async def _start_worker(self,worker,loop=None):
        self.workers.append(worker)
        module = worker.module
        self.worked_paths[module.destination.path]=worker
        inserter_task = None
        if(module.keep_data):
            my_inserter = inserter.NilmDbInserter(self.nilmdb_client,
                                    module.destination.path,
                                    decimate = module.destination.decimate)
            inserter_task = asyncio.ensure_future(my_inserter.process(worker.subscribe()),loop=loop)
        await worker.run()
        if(module.keep_data):
            my_inserter.stop()
            await inserter_task

    async def _db_committer(self,loop=None):
      while(not self.stop_requested):
          await asyncio.sleep(5)
          self.procdb.commit()
          
def load_configs(config_file):
    try:
        config_str = ''
        if(config_file is not None):
            with open(config_file) as f:
                config_str = f.read()
        return config_manager.load_configs(config_string=config_str)
    except Exception as e:
        logging.error("Error loading configuration: %s",str(e))
        exit(1)
    
def main(args=None):

    parser = argparse.ArgumentParser("Joule Daemon")
    parser.add_argument("--config")
    args = parser.parse_args(args)
    configs = load_configs(args.config)
    daemon = Daemon()

    try:
        daemon.initialize(configs)

    except DaemonError as e:
        print("Error starting jouled [%s]"%str(e))
        exit(1)
        
    loop=asyncio.get_event_loop()
    loop.set_debug(True)
    loop.add_signal_handler(signal.SIGINT,daemon.stop)
    daemon.run(loop)
    loop.close()
    exit(0)

