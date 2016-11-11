
"""
InputModule: Data Capture Process

Configuration File:
[Main]
name = module name
description = module description
exec = /path/to/file --args 

[Source]
path1 = /nilmdb/stream1
path2 = /nilmdb/stream2
  ....
pathN = /nilmdb/streamN

[Destination]
#required settings (examples)
path = /jouledb/directory/name
datatype = float
keep = 1w
#optional settings (defaults)
decimate = yes

[Stream1...StreamN]
#required settings (examples)
name         = Stream Name
#optional settings (defaults)
plottable    = yes
discrete     = no
offset       = 0.0
scale_factor = 0.0
default_max  = 0.0
default_min  = 0.0

"""

import logging
import re
import configparser
from .errors import ConfigError
from . import destination
from . import stream

STATUS_LOADED = 'loaded'
STATUS_FAILED = 'failed'
STATUS_RUNNING = 'running'
STATUS_UNKNOWN = 'unknown'

class InputModule(object):
    log = logging.getLogger(__name__)

    def __init__(self,
                 status = STATUS_UNKNOWN,
                 pid = -1, id = None,
                 config_file = ""):
        #persistent configuration info (can be restored from procdb)
        self.name = ""
        self.description = ""
        self.destination = None
        self.pid = pid
        self.id = id
        self.status = status
        self.source_paths = {}
        #if a config file is specified, parse it and initialize
        if(config_file != ""):
            config = configparser.ConfigParser()
            config.read(config_file)
            self.initialize(config)
            
    def initialize(self,config):
        try:
            self._load_info_configs(config['Main'])
            self._load_source_configs(config['Source'])
            self._load_destination_configs(config)
        except KeyError as e:
            raise ConfigError("Missing section [%s]"%e) from e
        
    def _load_info_configs(self,main_config):
        #initialize the module from the config file
        try:
            self.name = main_config['name']
            if(self.name==''):
                raise ConfigError("module name is missing or blank")
            self.description = main_config.get('description','')
            self.exec_cmd = main_config['exec']
            if(self.exec_cmd==''):
                raise ConfigError("module exec_cmd is missing or blank")
        except KeyError as e:
            raise ConfigError("In [main] missing [%s] setting"%e) from e
        
    def _load_source_configs(self,source_config):
        for name in source_config:
            try:
                path = source_config[name]
                destination.validate_path(path)
            except Exception as e:
                raise ConfigError("Invalid source stream [{:s}]".format(path)) from e
            self.source_paths[name]=path
            
    def _load_destination_configs(self,config):
        dest_parser = destination.Parser()
        stream_parser = stream.Parser()
        try:
            self.destination = dest_parser.run(config['Destination'])
            stream_configs = filter(lambda sec: re.match("Stream\d",sec),
                                    config.sections())
            for stream_config in stream_configs:
                new_stream = stream_parser.run(config[stream_config])
                self.destination.add_stream(new_stream)        
        except KeyError as e:
            raise ConfigError("missing [%s] section"%e.args[0]) from e
        #make sure we have at least one stream
        if(len(self.destination.streams)==0):
            raise ConfigError("missing stream configurations, must have at least one")
    
    def keep_data(self):
        """True if the destination is recording data (keep!=none)"""
        return self.destination.keep_us!=0

    def numpy_columns(self):
        return len(self.destination.streams)+1
    
            
    def __str__(self):
        if(self.name != ""):
            return self.name
        else:
            return "unknown name"
