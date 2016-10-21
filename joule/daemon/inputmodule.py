
"""
InputModule: Data Capture Process

Configuration File:
[Main]
name = module name
description = module description

[Source]
# pick exec OR fifo
generator = /path/to/python args
exec = /path/to/file --args 
fifo = /path/to/fifo

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
import shlex
import subprocess
import os
from .errors import ConfigError
from joule.utils import numpypipe
from . import destination
from . import stream

STATUS_LOADED = 'loaded'
STATUS_ERROR = 'error'
STATUS_RUNNING = 'running'
STATUS_UNKNOWN = 'unknown'

class InputModule(object):
    log = logging.getLogger(__name__)

    def __init__(self,
                 status = STATUS_UNKNOWN,
                 pid = None, id = None,
                 config_file = ""):
        #persistent configuration info (can be restored from procdb)
        self.name = ""
        self.description = ""
        self.destination = None
        self.pid = pid
        self.id = id
        self.status = status
        #runtime structures, cannot be restored from procdb
        self.process = None
        #if a config file is specified, parse it and initialize
        if(config_file != ""):
            config = configparser.ConfigParser()
            config.read(config_file)
            self.initialize(config)
            
    def initialize(self,config):
        #initialize the module from the config file
        try:
            self.name = config['Main']['name']
            if(self.name==''):
                raise KeyError
            self.description = config['Main'].get('description','')
            self.exec_path = config['Source']['exec']
        except KeyError as e:
            raise ConfigError("module name is missing or blank")

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
    
    def start(self):
        cmd = shlex.split(self.exec_path)
        (rpipe, wpipe) = os.pipe()
        proc = subprocess.Popen(cmd,stdin=None,stdout=wpipe,stderr=subprocess.STDOUT)
        os.close(wpipe)
        self.process = proc
        return numpypipe.NumpyPipe(rpipe,
                                   num_streams=len(self.destination.streams))


    def restart(self):
        self.stop()
        self.start()
        
    def stop(self):
        if(self.is_alive() == False):
            return
        self.process.terminate()
        try:
            self.process.wait(4)
        except subprocess.TimeoutExpired:
            self.process.kill()
            
    def is_alive(self):
        if(self.process is None):
            return False
        self.process.poll()
        if(self.process.returncode is not None):
            return False
        return True

    def __str__(self):
        if(self.name != ""):
            return self.name
        else:
            return "unknown name"
