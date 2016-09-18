import re
from .errors import ConfigError

class Destination(object):
    def __init__(self,path,datatype,keep_us,decimate):
        self.path = path
        self.datatype = datatype
        self.keep_us = keep_us
        self.decimate = decimate
        #initialize empty stream array
        self.streams = []

    def add_stream(self,new_stream):
        #make sure the stream name is unique
        for stream in self.streams:
            if(stream.name==new_stream.name):
                raise ConfigError("the name setting for each stream must be unique")
        self.streams.append(new_stream)

    @property
    def data_format(self):
        return "%s_%d"%(self.datatype,len(self.streams))
    
class Parser(object):
    def run(self,configs):
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
        valid_datatypes = ["uint%d"%x for x in [8,16,32,64]]+\
                          ["int%d"%x for x in [8,16,32,64]]+\
                          ["float%d"%x for x in [32,64]]
        if(not(datatype in valid_datatypes)):
            raise ConfigError("invalid [Destination] datatype "+
                              "[%s], choose from [%s]"%
                              (datatype,",".join(valid_datatypes)))
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
