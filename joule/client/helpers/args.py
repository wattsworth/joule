
import argparse
import sys
import os
import configparser
import dateparser
from typing import Tuple

from joule.errors import ConfigurationError

""" helpers for handling module arguments
    Complicated because we want to look for module_config
    and add these args but this should be transparent
    (eg, the -h flag should show the real help)
"""


def module_args():
    # build a dummy parser to look for module_config
    temp_parser = argparse.ArgumentParser()
    temp_parser.add_argument("--module_config", default="unset")
    arg_list = sys.argv[1:]   # ignore the program name
    stdout = sys.stdout
    sys.stdout = open(os.devnull, 'w')
    try:
        args = temp_parser.parse_known_args()[0]
        if args.module_config != "unset":
            arg_list += _append_args(args.module_config)
    except SystemExit:
        pass
    finally:
        sys.stdout.close()
        sys.stdout = stdout
    return arg_list


def _append_args(module_config_file):
    from joule.models import module
    # if a module_config is specified add its args
    module_config = configparser.ConfigParser()
    with open(module_config_file, 'r') as f:
        module_config.read_file(f)
    my_module = module.from_config(module_config)
    args = []
    for (arg, value) in my_module.arguments.items():
        args += ["--" + arg, value]
    return args


def read_module_config(file_path: str) -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    try:
        # can only happen if process does not have read permissions
        if len(config.read(file_path)) != 1:
            raise ConfigurationError("Cannot read module config [%s]" % file_path)
    except configparser.Error as e:
        raise ConfigurationError("Invalid module config: %s" % str(e))
    return config


def validate_time_bounds(start: str, end: str) -> Tuple[int, int]:
    if start is not None:
        start = int(dateparser.parse(start).timestamp() * 1e6)
    if end is not None:
        end = int(dateparser.parse(end).timestamp() * 1e6)
    if start is not None and end is not None:
        if start >= end:
            raise ConfigurationError("start [%d] must be < end [%d]" % (start, end))
    return start, end
