

import os
import configparser
import asyncio
from .inputmodule import InputModule
from .worker import Worker
from .errors import DaemonError
from . import stream, inputmodule
from joule.procdb import client as procdb_client
import logging
import functools
import argparse
import nilmdb.client
import nilmtools.filter
import signal
from joule.utils import config_manager
from . import inserter

class Daemon(object):
    log = logging.getLogger(__name__)
    
    def __init__(self):
        
        #populated by initialize
        self.procdb = None
        self.nilmdb_client = None
        self.stop_requested = False
        self.modules = []
        self.destinations = []
        
        #runtime structures
        self.path_workers = {} #subscriber dict
        self.path_destinations = {} #destination dict
        self.workers = []
        self.inserters = []
        
    def initialize(self,config):
        #Build a NilmDB client
        self.nilmdb_client = nilmdb.client.numpyclient.\
                             NumpyClient(config.nilmdb.url)

        #Set up the ProcDB
        self.procdb = procdb_client.SQLClient(config.procdb.db_path)
        self.procdb.clear_input_modules()            
        
        #Set up destinations
        path_dir = config.jouled.path_directory
        destinations = self._load_configs(path_dir,self._build_destination)
        self._register_items(destinations,self._validate_destination,self.destinations)
        for dest in self.path_destinations: #set up dictionary to find destination by path
            self.path_destinations[dest.path] = dest
        #Set up modules
        module_dir = config.jouled.module_directory
        modules = self._load_configs(module_dir,self._build_module)
        self._register_items(modules,self._validate_module,self.modules)

    def _load_configs(self,path,factory):
        objects = []
        for item in os.listdir(path):
            if(not item.endswith(".conf")):
                continue
            file_path = os.path.join(path,item)
            config = configparser.ConfigParser()
            config.read(file_path)
            obj = factory(config)
            if(obj is not None):
                objects.append(obj)
            
        return objects

    def _register_items(self,items,validator,store):
        """Validate destination, creating them if they are not present in NilmDB
           sets self.destinations"""
        for item in items:
            if(validator(item)):
                store.append(item)
        
    def _build_destination(self,config):
        """create a destination object from config
        """
        try:
            parser = destination.Parser()
            dest = parser.run(config)

        except destination.ConfigError as e:
            logging.error("Cannot load destination config: \n\t%s"%e)
            return None
        return dest

    def _validate_destination(self,destination):
        client = self.nilmdb_client
        info = nilmtools.filter.get_stream_info(client,destination.path)
        #1.) Validate or create the destination in NilmDB
        if info:
            #path exists, make sure the structure matches what this destination wants
            if(info.layout_type != destination.datatype):
                logging.error("Destination [%s]: the path [%s] has datatype [%s], this uses [%s]"%
                                  (destination.name,destination.path,
                                   info.layout_type,destination.datatype))
                return False
            if(info.layout != destination.data_format):
                print("%s != %s"%(info.layout,destination.data_format))
                logging.error("Destination [%s]: the path[%s] has [%d] streams, this has [%d]"%
                                  (destination.name, destination.path,
                                   info.layout_count, len(destination.streams)))
                return False
            #datatype and stream count match so we are ok
        else:
            client.stream_create(destination.path,"%s_%d"%
                                 (destination.datatype,len(destination.streams)))
        #2.) Make sure no other destination config is using this path
        for dest in self.destinations:
            if(dest.path==destination.path):
                logging.error("Destination [%s]: the path [%s] is already used by [%s]"%
                              (destination.name,dest.path,dest.name))
                return False
        #OK, all checks passed for this destination
        return True
    
    def _build_module(self,config):
        """ create an input module from config
        """
        module = InputModule()
        try:
            module.initialize(config)
        except inputmodule.ConfigError as e:
            self.log.error("Cannot load module config: \n\t%s"%(e))
            return None
        return module

    def _validate_module(self,module):

        for path in module.destination_paths.values():
            #1.) Make sure all destinations have configurations
            if(not path in self.path_destinations):
                logging.error("Module [%s]: destination [%s] has no configuration"%
                              (module.name,path))
                return False
            #2.) Make sure destinations are unique among modules
            used_paths = [m.destination_paths.values() for m in self.modules]
            for paths in used_paths:
                if(path in paths):
                    logging.error("Module [%s]: destination [%s] is already used"%
                                  (module.name,path))
                    return False
        #OK: all checks passed for this module
        return True

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
                if(w.register_inputs(self.path_workers)):
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


    async def _start_worker(self,worker,loop=None):
        self.workers.append(worker)
        module = worker.module
        my_inserters = []
        for path in module.destination_paths.values():
            self.path_workers[path] = functools.partial(worker.subscribe,path)
            destination = self.destination_paths[path]
            if(destination.keep_data):
                i = inserter.NilmDbInserter(self.nilmdb_client,
                                            path,
                                            decimate = destination.decimate)
                asyncio.ensure_future(i.process(worker.subscribe(path)),loop=loop)
                my_inserters.append(i)
        #waits here while worker runs
        await worker.run()
        #execute shutdown tasks
        for i in my_inserters:
            i.stop()

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

