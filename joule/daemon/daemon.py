

import os
import configparser
import asyncio
from .inputmodule import InputModule
from .worker import Worker
from .errors import DaemonError
from joule.procdb import client as procdb_client
import logging

import argparse
import signal
import nilmdb.client
from joule.utils import config_manager
from . import inserter

PROC_DB = "/tmp/joule-proc-db.sqlite"

class Daemon(object):
    log = logging.getLogger(__name__)
    
    def __init__(self):
        self.input_modules = []
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

    def run(self):
        loop = asyncio.get_event_loop()
        #start each module and store runtime structures in a worker
        for module in self.input_modules:
            asyncio.ensure_future(self._start_worker(module))

        loop.run_forever()
        loop.close()
        
    def stop(self):
        self.run_flag = False
        for worker in self.workers:
            worker.stop()
            worker.join()

    async def _start_worker(self,module):
        worker = Worker(module,procdb_client=self.procdb)
        if(module.keep_data):
            my_inserter = inserter.NilmDbInserter(self.nilmdb_client,
                                    module.destination.path,
                                    decimate = module.destination.decimate)
            asyncio.ensure_future(my_inserter.process(worker.subscribe()))
        asyncio.ensure_future(worker.run())
        

daemon = Daemon()

def handler(signum, frame):
    print("handler called with signum: ",signum)
    daemon.stop()
    
def main():
    parser = argparse.ArgumentParser("Joule Daemon")
    parser.add_argument("--config")
    args = parser.parse_args()

    try:
        config_str = ''
        if(args.config is not None):
            with open(args.config) as f:
                config_str = f.read()
        my_configs = config_manager.load_configs(config_string=config_str)
    except Exception as e:
        logging.error("Error loading configuration: %s",str(e))
        exit(1)
        
    try:
        daemon.initialize(my_configs)
    except DaemonError as e:
        print(e)
        print("cannot recover, exiting")
        exit(1)
        
    signal.signal(signal.SIGINT, handler)
    daemon.run()
    
if __name__=="__main__":
    main()
