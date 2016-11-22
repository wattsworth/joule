

import os
import configparser
import asyncio
from .worker import Worker
from .errors import DaemonError
from . import stream, module
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
        self.streams = []

        #constants customized by initialize
        self.NILMDB_INSERTION_PERIOD=5
        
        #runtime structures
        self.path_workers = {} #key: path, value: fn_subscribe()
        self.path_streams = {} #key: path, value: stream
        self.workers = []
        self.inserters = []
        
    def initialize(self,config):
        #Build a NilmDB client
        self.nilmdb_client = nilmdb.client.numpyclient.\
                             NumpyClient(config.nilmdb.url)

        #Set up the ProcDB
        self.procdb = procdb_client.SQLClient(config.procdb.db_path)
        self.procdb_commit_interval = 5 #commit every 5 seconds
        self.procdb.clear_db()
        
        #Set up streams
        stream_dir = config.jouled.stream_directory
        streams = self._load_configs(stream_dir,self._build_stream)
        self._register_items(streams,self._validate_stream,self.streams)
        for my_stream in self.streams: #set up dictionary to find stream by path
            self.path_streams[my_stream.path] = my_stream
        #Set up modules
        module_dir = config.jouled.module_directory
        modules = self._load_configs(module_dir,self._build_module)
        self._register_items(modules,self._validate_module,self.modules)

        #Configure tunable constants
        self.NILMDB_INSERTION_PERIOD = config.nilmdb.insertion_period
        
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
        """Validate stream, creating them if they are not present in NilmDB
           sets self.streams"""
        for item in items:
            if(validator(item)):
                store.append(item)
        
    def _build_stream(self,config):
        """create a stream object from config
        """
        try:
            parser = stream.Parser()
            my_stream = parser.run(config)

        except stream.ConfigError as e:
            logging.error("Cannot load stream config: \n\t%s"%e)
            return None
        return my_stream

    def _validate_stream(self,my_stream):
        client = self.nilmdb_client
        info = nilmtools.filter.get_stream_info(client,my_stream.path)
        #1.) Validate or create the stream in NilmDB
        if info:
            #path exists, make sure the structure matches what this stream wants
            if(info.layout_type != my_stream.datatype):
                logging.error("Stream [%s]: the path [%s] has datatype [%s], this uses [%s]"%
                                  (my_stream.name,my_stream.path,
                                   info.layout_type,my_stream.datatype))
                return False
            if(info.layout != my_stream.data_format):
                logging.error("Stream [%s]: the path[%s] has [%d] elements, this has [%d]"%
                                  (my_stream.name, my_stream.path,
                                   info.layout_count, len(my_stream.elements)))
                return False
            #datatype and element count match so we are ok
        else:
            client.stream_create(my_stream.path,my_stream.data_format)
        #2.) Make sure no other stream config is using this path
        for other_stream in self.streams:
            if(my_stream.path==other_stream.path):
                logging.error("Stream [%s]: the path [%s] is already used by [%s]"%
                              (my_stream.name,my_stream.path,other_stream.name))
                return False
        #OK, all checks passed for this stream
        return True
    
    def _build_module(self,config):
        """ create an input module from config
        """
        parser = module.Parser()
        try:
            my_module = parser.run(config)
        except module.ConfigError as e:
            self.log.error("Cannot load module config: \n\t%s"%(e))
            return None
        return my_module

    def _validate_module(self,module):

        for path in module.destination_paths.values():
            #1.) Make sure all destinations have matching streams
            if(not path in self.path_streams):
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
        for path in module.source_paths.values():
            #1.) Make sure all sources have matching streams
            if(not path in self.path_streams):
                logging.error("Module [%s]: source [%s] has no configuration"%
                              (module.name,path))
                return False

        #OK: all checks passed for this module
        return True

    def run(self,loop):
        """start each module and store runtime structures in a worker"""
        #only call this function once, error if called twice
        assert(len(self.workers)==0)
        tasks = []

        #loop through modules until they are all registered and started
        #if a module's inputs have no matching outputs, it can't run

        pending_workers = [Worker(m,procdb_client = self.procdb)
                           for m in self.modules]
        while(len(pending_workers)>0):
            started_a_worker = False
            for w in pending_workers:
                if(w.register_inputs(self.path_workers)):
                    tasks.append(self._start_worker(w,loop=loop))
                    pending_workers.remove(w)
                    started_a_worker = True
            if(started_a_worker==False):
                for w in pending_workers:
                    logging.warning("Could not start %s because nobody is producing its inputs"%
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
            stream = self.path_streams[path]
            #build inserters for any paths that have non-zero keeps
            if(stream.keep_data):
                i = inserter.NilmDbInserter(self.nilmdb_client,
                                            path,
                                            insertion_period=self.NILMDB_INSERTION_PERIOD,
                                            decimate = stream.decimate)
                asyncio.ensure_future(i.process(worker.subscribe(path)),loop=loop)
                my_inserters.append(i)
        #waits here while worker runs
        await worker.run()
        #execute shutdown tasks
        for i in my_inserters:
            i.stop()

    async def _db_committer(self,loop=None):
      while(not self.stop_requested):
          await asyncio.sleep(self.procdb_commit_interval)
          self.procdb.commit()
          
def load_configs(config_file):
    configs = {}
    if(config_file is not None):
        if(os.path.isfile(config_file)==False):
            raise config_manager.\
                InvalidConfiguration("cannot load file [%s]"%config_file)
        configs = configparser.ConfigParser()
        configs.read(config_file)
    return config_manager.load_configs(configs=configs)
    
def main(argv=None):
    parser = argparse.ArgumentParser("Joule Daemon")
    parser.add_argument("--config")
    args = parser.parse_args(argv)
    daemon = Daemon()

    try:
        configs = load_configs(args.config)
    except Exception as e:
        logging.error("Error loading configs: %s"%str(e))
        exit(1)
    try:
        daemon.initialize(configs)
    except DaemonError as e:
        logging.error("Error starting jouled [%s]"%str(e))
        exit(1)
        
    loop=asyncio.get_event_loop()
    loop.set_debug(True)
    loop.add_signal_handler(signal.SIGINT,daemon.stop)
    daemon.run(loop)
    loop.close()
    exit(0)

