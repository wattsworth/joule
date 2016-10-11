

import os
import configparser
from .inputmodule import InputModule
from .errors import DaemonError, ConfigError
from joule.procdb import client as procdb_client
import logging
import time
import argparse
import collections
import threading
import signal
import nilmdb.client
from . import defaults, inserter

class Daemon(object):
    log = logging.getLogger(__name__)
    
    def __init__(self):
        self.input_modules = []
        self.workers = []

    def initialize(self,config):
        procdb_client.clear_input_modules()
        
        try:
            #Build a NilmDB client
            nilmdb_url = config["Main"]["NilmdbURL"]
            self.nilmdb_client = nilmdb.client.numpyclient.\
                                 NumpyClient(nilmdb_url)
            #Set up the input modules
            module_dir = config["Main"]["InputModuleDir"]
            for module_config in os.listdir(module_dir):
                if(not module_config.endswith(".conf")):
                    continue
                config_path = os.path.join(module_dir,module_config)
                self._build_module(config_path)
        except KeyError as e:
            raise ConfigError(e) from e
        except FileNotFoundError as e:
            raise ConfigError("InputModuleDir [%s] does not exist"%
                              module_dir) from e

        
    def _build_module(self,module_config):
        """ create an input module from config file
        """
        config = configparser.ConfigParser()
        config.read(module_config)
        module = InputModule()
        try:
            module.initialize(config)
            procdb_client.register_input_module(module,module_config)
        except (DaemonError, procdb_client.ConfigError) as e:
            self.log.error("Cannot load module [%s]: \n\t%s"%(module_config,e))
            return
        self.input_modules.append(module)

    def run(self):
        self.run_flag = True        
        #start each module and store runtime structures in a worker
        for module in self.input_modules:
            self._start_worker(module)

        #start the inserter thread
        inserter_thread = threading.Thread(self._run_inserters)
        inserter_thread.start()

        while(self.run_flag):
            time.sleep(1)

        #stop requested, shut down workers
        for worker in self.workers:
            worker.join()
        for inserter in self.inserters:
            inserter.finalize()
        inserter_thread.join()

        print("stopped")
        
    def stop(self):
        self.run_flag = False
        for worker in self.workers:
            worker.stop()
        print("stopping...")


    def _start_worker(self,module):
        worker = Worker(module)
        if(module.keep_data):
            inserter = inserters.NilmDbInserter(self.client,
                            module.destination.path,
                            decimate = module.destination.decimate)
            worker.subscribe(inserter.queue)
            self.inserters.append(inserter)
        self.workers.append(worker)

    def _run_inserters(self):
        for inserter in self.inserters:
            inserter.process_data()
        time.sleep(5)
        
Worker = collections.namedtuple("Worker",["module","process","q_out","db_inserter"])

daemon = Daemon()

def handler(signum, frame):
    print("handler called with signum: ",signum)
    daemon.stop()
    
def main():
    parser = argparse.ArgumentParser("Joule Daemon")
    parser.add_argument("--config")
    args = parser.parse_args()

    config = configparser.ConfigParser()
    if(not os.path.isfile(args.config)):
        print("Error, cannot load configuration file [%s], specify with --config"%args.config)
        return -1


    config.read_dict(defaults.config)
    config.read(args.config)
    try:
        daemon.initialize(config)
    except DaemonError as e:
        print(e)
        print("cannot recover, exiting")

    signal.signal(signal.SIGINT, handler)
    daemon.run()
    
