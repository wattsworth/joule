
"""
InputModule: Data Capture Process

Configuration File:
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
from .errors import ConfigError
from . import destination

class InputModule(object):
    log = logging.getLogger(__name__)

    def __init__(self):
        self.destination = None
    
    def initialize(self,configs):
        dest_parser = destination.Parser()
        try:
            self.destination = dest_parser.run(configs['Destination'])
        except KeyError as e:
            raise ConfigError("missing [%s] section"%e.args[0]) from e
        
        


