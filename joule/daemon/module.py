
"""
InputModule: Data Capture Process

Configuration File:
[Main]
name = module name
description = module description
exec = /path/to/file --args 

[Source]
path1 = /nilmdb/input/stream1
path2 = /nilmdb/input/stream2
  ....
pathN = /nilmdb/input/streamN

[Destination]
path1 = /nilmdb/output/stream1
path2 = /nilmdb/output/stream2
  ....
pathN = /nilmdb/output/streamN
"""

import logging
from .errors import ConfigError
from . import stream

STATUS_LOADED = 'loaded'
STATUS_FAILED = 'failed'
STATUS_RUNNING = 'running'
STATUS_UNKNOWN = 'unknown'

class Module(object):
    log = logging.getLogger(__name__)

    def __init__(self,name,description,exec_cmd,source_paths,destination_paths,
                 status=STATUS_UNKNOWN,pid = -1,id = None):

        self.name = name
        self.description = description
        self.exec_cmd = exec_cmd
        self.source_paths = source_paths
        self.destination_paths = destination_paths

        self.status = status
        self.pid = pid
        self.id = id


    def __eq__(self,other):
        return self.__dict__==other.__dict__

    def __lt__(a,b):
        return a.id<b.id

    def __gt__(a,b):
        return a.id>b.id

    def __str__(self):
        if(self.name != ""):
            return "Module [%s]"%self.name
        else:
            return "Module [unknown name]"

        
class Parser(object):
    def run(self,configs):
        try:
            main_configs = configs["Main"]
            source_paths = self._load_paths(configs['Source'])
            destination_paths = self._load_paths(configs['Destination'])
        except KeyError as e:
            raise ConfigError("Missing section [%s]"%e) from e            
        try:
            name = main_configs["name"]
            if(name==''):
                raise ConfigError("name is missing or blank")
            description = main_configs.get('description','')
            exec_cmd = main_configs["exec_cmd"]
            if(exec_cmd==''):
                raise ConfigError("exec_cmd is missing or blank")
        except KeyError as e:
            raise ConfigError("In [main] missing [%s] setting"%e) from e
        return Module(name,description,exec_cmd,source_paths,destination_paths)

    def _load_paths(self,config):
        paths = {}
        for name in config:
            try:
                path = config[name]
                stream.validate_path(path)
            except Exception as e:
                raise ConfigError("Invalid path [{:s}]".format(path)) from e
            paths[name]=path
        return paths
    
