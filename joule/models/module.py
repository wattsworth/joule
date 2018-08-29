import enum
from typing import Dict
import configparser

from joule.errors import ConfigurationError
from joule.models.stream import Stream

"""
Configuration File:
[Main]
name = module name
description = module description
exec_cmd = /path/to/file
has_interface = no

[Arguments]
key = value

[Inputs]
#name = full_path:<stream config>
labjack = /labjack/device3/data:float32[e0,e1,e2]
path2 = /nilmdb/input/stream2
  ....
pathN = /nilmdb/input/streamN

[Outputs]
#name = full_path:<stream config>
path1 = /nilmdb/output/stream1:float32[x,y,z]
path2 = /nilmdb/output/stream2
  ....
pathN = /nilmdb/output/streamN
"""


class Module:
    class STATUS(enum.Enum):
        LOADED = enum.auto()
        RUNNING = enum.auto()
        FAILED = enum.auto()
        UNKNOWN = enum.auto()

    def __init__(self, name: str, exec_cmd: str, description: str = "",
                 log_size: int = 100,
                 has_interface: bool = False, uuid: int = None):
        self.name = name
        self.exec_cmd = exec_cmd
        self.description = description
        self.has_interface = has_interface
        self.log_size = log_size
        # arg_name => value
        self.arguments: Dict[str, str] = {}
        # pipe name (from config) => stream object
        self.inputs: Dict[str, Stream] = {}
        self.outputs: Dict[str, Stream] = {}
        self.uuid: int = uuid
        self.status: Module.STATUS = Module.STATUS.UNKNOWN

    def __repr__(self):
        return "<Module(uuid=%r, name=%s)>" % (self.uuid, self.name)

    def to_json(self):
        return {
            'id': self.uuid,
            'name': self.name,
            'description': self.description,
            'exec_cmd': self.exec_cmd,
            'has_interface': self.has_interface,
            'arguments': self.arguments,
            'inputs': dict((name, stream.id) for (name, stream) in self.inputs.items()),
            'outputs': dict((name, stream.id) for (name, stream) in self.outputs.items())
        }


def from_config(config: configparser.ConfigParser) -> Module:
    try:
        main_configs: configparser.ConfigParser = config["Main"]
    except KeyError as e:
        raise ConfigurationError("Missing section [%s]" % e.args[0]) from e
    try:
        name = validate_name(main_configs["name"])
        description = main_configs.get("description", fallback="")
        exec_cmd = main_configs["exec_cmd"]
        has_interface = main_configs.getboolean("has_interface", fallback=False)
    except KeyError as e:
        raise ConfigurationError("[Main] missing %s" % e.args[0]) from e
    my_module = Module(name=name, description=description, exec_cmd=exec_cmd,
                       has_interface=has_interface)
    # parse the arguments
    if 'Arguments' in config:
        for name, value in config['Arguments'].items():
            my_module.arguments[name] = value
    return my_module


def validate_name(name: str) -> str:
    if len(name) == 0:
        raise ConfigurationError("missing name")
    return name
