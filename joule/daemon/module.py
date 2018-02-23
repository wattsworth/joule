
"""
InputModule: Data Capture Process

Configuration File:
[Main]
name = module name
description = module description
exec_cmd = /path/to/file
web_interface = no

[Arguments]
key = value

[Inputs]
path1 = /nilmdb/input/stream1
path2 = /nilmdb/input/stream2
  ....
pathN = /nilmdb/input/streamN

[Outputs]
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

    def __init__(self,
                 name,
                 description,
                 web_interface,
                 exec_cmd,
                 args,
                 input_paths,
                 output_paths,
                 status=STATUS_UNKNOWN,
                 pid=-1,
                 id=None,
                 socket=None):

        self.name = name
        self.description = description
        self.web_interface = web_interface
        self.exec_cmd = exec_cmd  # this should have args built-in
        self.args = args  # --arg=value
        self.input_paths = input_paths
        self.output_paths = output_paths

        self.status = status
        self.pid = pid
        self.id = id
        self.socket = socket

    def to_json(self):
        return self.__dict__
    
    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __lt__(a, b):
        return a.id < b.id

    def __gt__(a, b):
        return a.id > b.id

    def __str__(self):
        if(self.name != ""):
            return "Module [%s]" % self.name
        else:
            return "Module [unknown name]"


class Parser(object):

    def run(self, configs):
        try:
            main_configs = configs["Main"]
            input_paths = self._load_paths(configs['Inputs'])
            output_paths = self._load_paths(configs['Outputs'])
        except KeyError as e:
            raise ConfigError("Missing section [%s]" % e) from e
        try:
            name = main_configs["name"]
            if(name == ''):
                raise ConfigError("name is missing or blank")
            description = main_configs.get('description', '')
            web_interface = main_configs.getboolean('web_interface', False)
            exec_cmd = main_configs["exec_cmd"]
            if(exec_cmd == ''):
                raise ConfigError("exec_cmd is missing or blank")
            if "Arguments" in configs:
                args = self._compile_arguments(configs["Arguments"])
                exec_cmd += self._stringify_arguments(configs["Arguments"])
            else:
                args = []
            return Module(name, description, web_interface,
                          exec_cmd, args, input_paths, output_paths)
        except KeyError as e:
            raise ConfigError("In [main] missing [%s] setting" % e) from e

    def _compile_arguments(self, args):
        arg_list = []
        if args is None:
            return arg_list
        for key in args:
            arg_list.append('--%s' % key)
            if(args[key] is not None and
               len(args[key]) > 0):
                arg_list.append("%s" % args[key])
        return arg_list
        
    def _stringify_arguments(self, args):
        arg_list = ""
        if args is None:
            return arg_list
        for key in args:
            arg_list += ' --%s' % key
            if(args[key] is not None and
               len(args[key]) > 0):
                arg_list += '="%s"' % args[key]
        return arg_list
    
    def _load_paths(self, config):
        paths = {}
        for name in config:
            try:
                path = config[name]
                stream.validate_path(path)
            except Exception as e:
                raise ConfigError("Invalid path [{:s}]".format(path)) from e
            paths[name] = path
        return paths
