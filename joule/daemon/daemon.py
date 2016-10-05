

import os
import configparser
from .inputmodule import InputModule
from .errors import DaemonError, ConfigError
from joule.procdb import client as procdb_client
import logging
import time
import argparse
import collections
import multiprocessing as mp
import signal

class Daemon(object):
    log = logging.getLogger(__name__)
    
    def __init__(self):
        self.input_modules = []
        self.workers = []

    def initialize(self,config):
        procdb_client.clear_input_modules()
        try:
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
        #start each module and store runtime structures in a worker
        for module in self.input_modules:
            q_out = mp.Queue()
            p = module.start(queue_out = q_out)
            procdb_client.update_module(module)
            worker = Worker(module,p,q_out)
            self.workers.append(worker)
        self.run_flag = True
        while(self.run_flag):
            for worker in self.workers:
                if(not worker.q_out.empty):
                    pass #write to database
                if(not worker.process.is_alive()):
                    print("worker %d finished with exit code: ",worker.module.pid,worker.process.exitcode)
                    print("restarting worker")
            time.sleep(1)
        #stop requested, shut down workers
        for worker in self.workers:
            if(worker.process.is_alive()):
                worker.process.terminate()
        print("stopped")
        
    def stop(self):
        self.run_flag = False
        print("stopping...")
        
Worker = collections.namedtuple("Worker",["module","process","q_out"])

daemon = Daemon()

def handler(signum, frame):
    print("handler called with signum: ",signum)
    daemon.stop()
    
def main():
    parser = argparse.ArgumentParser("Joule Daemon")
    parser.add_argument("--config",default="/etc/joule/joule.conf")
    args = parser.parse_args()

    config = configparser.ConfigParser()
    if(not os.path.isfile(args.config)):
        print("Error, cannot load configuration file [%s], specify with --config"%args.config)
        return -1
    
    config.read(args.config)
    try:
        daemon.initialize(config)
    except DaemonError as e:
        print(e)
        print("cannot recover, exiting")

    signal.signal(signal.SIGINT, handler)
    daemon.run()
    
