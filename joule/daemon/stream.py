"""
Stream: NilmDB stream 

[Main]
path = /nilmdb/path/name
datatype = float
keep = 1w
#optional settings (defaults)
decimate = yes

[Element1...ElementN]
#required settings (examples)
name         = Element Name
#optional settings (defaults)
description  = 
plottable    = yes
discrete     = no
offset       = 0.0
scale_factor = 0.0
default_max  = 0.0
default_min  = 0.0

"""

import re
from .errors import ConfigError
from . import element

class Stream(object):
    def __init__(self,name,description,path,datatype,
                 keep_us,decimate,id=None):
        self.path = path
        self.datatype = datatype
        self.keep_us = keep_us
        self.decimate = decimate
        self.name = name
        self.description = description
        #set by procdb
        self.id = id
        #initialize empty element array
        self.elements = []

    def __eq__(self,other):
        return self.__dict__==other.__dict__

    def __str__(self):
        return "Stream [{name}] @ [{path}]".format(name=self.name,path=self.path)

    def __lt__(a,b):
        return a.id<b.id

    def __gt__(a,b):
        return a.id>b.id
    
    def add_element(self,new_element):
        #make sure the element name is unique
        for s in self.elements:
            if(s.name==new_element.name):
                raise ConfigError("the name setting for each element must be unique")
        self.elements.append(new_element)

    @property
    def data_format(self):
        return "%s_%d"%(self.datatype,len(self.elements))

    @property
    def data_width(self):
        return len(self.elements)+1

def validate_path(path):
    if(re.fullmatch('^(\/\w+)(\/\w+)+$',path) is None):
        raise ConfigError("invalid stream path, use format: /dir/subdir/../file")
    return path

class Parser(object):
    def run(self,configs):
        main_configs = configs["Main"]
        try:
            path = validate_path(main_configs["path"])
            datatype = self._validate_datatype(main_configs["datatype"])
            keep_us = self._validate_keep(main_configs["keep"])
            decimate = main_configs.getboolean("decimate",fallback=True)
            name = main_configs["name"]
            description = main_configs["description"]
            my_stream =  Stream(name,description,path,datatype,keep_us,decimate)
        except KeyError as e:
            raise ConfigError("[Main] missing %s"%e.args[0])
        #now try to load the elements
        element_configs = filter(lambda sec: re.match("Element\d",sec),
                                configs.sections())
        for name in element_configs:
            element_parser = element.Parser()
            new_element = element_parser.run(configs[name])
            my_stream.add_element(new_element)
        #make sure we have at least one element
        if(len(my_stream.elements)==0):
            raise ConfigError("missing element configurations, must have at least one")
        return my_stream
    
    def _validate_datatype(self,datatype):
        valid_datatypes = ["uint%d"%x for x in [8,16,32,64]]+\
                          ["int%d"%x for x in [8,16,32,64]]+\
                          ["float%d"%x for x in [32,64]]
        if(not(datatype in valid_datatypes)):
            raise ConfigError("invalid [Stream] datatype "+
                              "[%s], choose from [%s]"%
                              (datatype,",".join(valid_datatypes)))
        return datatype
    
    def _validate_keep(self,keep):
        if keep.lower()=="none":
            return 0
        match = re.fullmatch('^(\d)([h|d|w|m|y])$',keep)
        if(match is None):
            raise ConfigError("invalid [Stream] keep, \
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
            raise ConfigError("invalid [Stream] keep, \
            invalid time (use No to avoid keeping data)")
        return time*units[unit]

