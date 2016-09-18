
"""
InputModule: Data Capture Process

Configuration File:
[Main]
name = module name
description = module description

[Source]
# pick exec OR fifo
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
from .errors import ConfigError
from . import destination
from . import stream

STATUS_LOADED = 'loaded'
STATUS_ERROR = 'error'
STATUS_RUNNING = 'running'

class InputModule(object):
    log = logging.getLogger(__name__)

    def __init__(self, name ="", description="", destination=None):
        self.name = name
        self.description = description
        self.destination = destination
    
    def initialize(self,config):
        try:
            self.name = config['Main']['name']
            if(self.name==''):
                raise KeyError
            self.description = config['Main'].get('description','')
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
        


