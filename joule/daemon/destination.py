import collections
import re
from .errors import ConfigError

Destination = collections.namedtuple('DbFile',
                                     ['path',
                                      'datatype',
                                      'keep_us',
                                      'decimate'])

class Parser(object):
    def run(self,configs):
        #1.) Configure the destination
        try:
            path = self._validate_path(configs["path"])
            datatype = self._validate_datatype(configs["datatype"])
            keep_us = self._validate_keep(configs["keep"])
            decimate = configs.getboolean("decimate",fallback=True)
            return Destination(path,datatype,keep_us,decimate)
        except KeyError as e:
            raise ConfigError("[Destination] missing %s"%e.args[0])
        
    def _validate_path(self,path):
        if(re.fullmatch('^(\/\w+)(\/\w+)+$',path) is None):
            raise ConfigError("invalid [Destination] path, \
            use format: /dir/subdir/../file")
        return path
    
    def _validate_datatype(self,datatype):
        if(not(datatype in ["float32","uint8","int"])):
            raise ConfigError("invalid [Destination] datatype")
        return datatype
    
    def _validate_keep(self,keep):
        match = re.fullmatch('^(\d)([h|d|w|m|y])$',keep)
        if(match is None):
            raise ConfigError("invalid [Destination] keep, \
            use format #unit (eg 1w)")

        units = {
            'h': 60*60*1e6,        #hours
            'd': 24*60*60*1e6,     #days
            'w': 7*24*60*60*1e6,   #weeks
            'm': 4*7*24*60*60*1e6, #months
            'y': 365*24*60*60*1e6  #years
        }
        unit = match.group(2)
        time = int(match.group(1))
        if(time<=0):
            raise ConfigError("invalid [Destination] keep, \
            invalid time (use No to avoid keeping data)")
        return time*units[unit]
