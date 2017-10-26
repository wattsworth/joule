import collections
from .errors import ConfigError

Element = collections.namedtuple("Element", ["name",
                                             "units",
                                             "plottable",
                                             "discrete",
                                             "offset",
                                             "scale_factor",
                                             "default_max",
                                             "default_min"])


def build_element(name, units="", plottable=True, discrete=False,
                  offset=0.0, scale_factor=1.0, default_max=None,
                  default_min=None):
    """Builds an element with default values"""
    return Element(name, units, plottable, discrete, offset, scale_factor,
                   default_max, default_min)


class Parser(object):

    def run(self, configs):
        self.config_name = configs.name  # for error reporting
        name = self._validate_name(configs["name"])
        if("units" in configs):
            units = configs["units"]
        else:
            units = ""
        plottable = self._get_bool("plottable", configs, True)
        discrete = self._get_bool("discrete", configs, False)
        offset = self._get_float("offset", configs, 0.0)
        scale_factor = self._get_float("scale_factor", configs, 1.0)
        default_max = self._get_float("default_max", configs, None)
        default_min = self._get_float("default_min", configs, None)
        self._validate_bounds(default_max, default_min)
        return Element(name, units, plottable, discrete, offset,
                       scale_factor, default_max, default_min)

    def _validate_name(self, name):
        if(name == ""):
            raise ConfigError("[%s] missing name" % self.config_name)
        return name

    def _validate_bounds(self, max, min):
        if(max is None or min is None):
            return
        if(min >= max):
            raise ConfigError("[%s] set default_min<default_max or use 0 for autoscale" %
                              self.config_name)

    def _get_bool(self, setting, configs, default):
        try:
            return configs.getboolean(setting, default)
        except ValueError as e:
            raise ConfigError("[%s] invalid value, use True/False" % setting)

    def _get_float(self, setting, configs, default):
        try:
            if(configs[setting] == "None"):
                return default
            return configs.getfloat(setting, default)
        except ValueError as e:
            raise ConfigError("[%s] bad value for %s, must be a number" %
                              (configs.name, setting)) from e
