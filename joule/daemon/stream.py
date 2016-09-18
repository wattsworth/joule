
import collections
from .errors import ConfigError

Stream = collections.namedtuple("Stream",["name",
                                          "plottable",
                                          "discrete",
                                          "offset",
                                          "scale_factor",
                                          "default_max",
                                          "default_min"])
def build_stream(name,plottable=True,discrete=False,
                 offset=0,scale_factor=0,default_max=0,
                 default_min=0):
    """Builds a stream with default values"""
    return Stream(name,plottable,discrete,offset,scale_factor,
                  default_max, default_min)
"""

class Stream(object):
    def __init__(self,name,
                 plottable=True,
                 discrete=False,
                 offset = 0.0,
                 scale_factor = 0.0,
                 default_max = 0.0,
                 default_min = 0.0):
        self.name = name
        self.plottable = plottable
        self.discrete = discrete
        self.offset = offset
        self.scale_factor = scale_factor
        self.default_max = default_max
        self.default_min = default_min
 """       
class Parser(object): 
    def run(self,configs):
        self.config_name = configs.name #for error reporting
        name         = self._validate_name(configs["name"])
        plottable    = configs.getboolean("plottable",True)
        discrete     = configs.getboolean("discrete",False)
        offset       = self._get_float("offset",configs,0.0)
        scale_factor = self._get_float("scale_factor",configs,1.0)
        default_max  = self._get_float("default_max",configs,0.0)
        default_min  = self._get_float("default_min",configs,0.0)
        self._validate_bounds(default_max,default_min)
        return Stream(name,plottable,discrete,offset,
                      scale_factor,default_max,default_min)

    def _validate_name(self,name):
        if(name==""):
            raise ConfigError("[%s] missing name"%self.config_name)
        return name
    def _validate_bounds(self,max,min):
        if(max==0 and min==0):
            return
        if(min>=max):
            raise ConfigError("[%s] set default_min<default_max or use 0 for autoscale"%
                              self.config_name)

    def _get_float(self,setting,configs,default):
        try:
            return configs.getfloat(setting,default)
        except ValueError as e:
            raise ConfigError("[%s] bad value for %s, must be a number"%
                              (configs.name,setting)) from e
