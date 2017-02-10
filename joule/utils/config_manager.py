"""
Configuration data structure for joule
Use load_configs to retrieve Configs object
"""

from collections import namedtuple
import configparser
import os

Configs = namedtuple('Configs', ['procdb', 'jouled', 'nilmdb'])
ProcdbConfigs = namedtuple('ProcdbConfigs', ['db_path', 'max_log_lines'])
NilmDbConfigs = namedtuple('NilmdbConfigs', ['url',
                                             'insertion_period',
                                             'cleanup_period'])
JouledConfigs = namedtuple(
    'JouledConfigs', ['module_directory', 'stream_directory'])

DEFAULT_CONFIG = {
    "NilmDB":
    {
        "URL": "http://localhost/nilmdb",
        "InsertionPeriod": 5,
        "CleanupPeriod": 600
    },
    "ProcDB":
    {
        "DbPath": "/tmp/joule-proc-db.sqlite",
        "MaxLogLines": 100
    },
    "Jouled":
    {
        "ModuleDirectory": "/etc/joule/module_configs",
        "StreamDirectory": "/etc/joule/stream_configs"
    }
}


def parse_procdb_configs(procdb_parser, verify):
    try:
        max_log_lines = int(procdb_parser['MaxLogLines'])
        if (max_log_lines < 0):
            raise Exception()
    except:
        raise InvalidConfiguration(
            "ProcDB:MaxLogLines must be integer greater than 0")

    return ProcdbConfigs(db_path=procdb_parser['DbPath'],
                         max_log_lines=max_log_lines)


def parse_jouled_configs(jouled_parser, verify):
    module_directory = jouled_parser['ModuleDirectory']
    if(not os.path.isdir(module_directory) and verify):
        raise InvalidConfiguration(
            "ModuleDirectory [%s] does not exist" % module_directory)
    stream_directory = jouled_parser['StreamDirectory']
    if(not os.path.isdir(stream_directory) and verify):
        raise InvalidConfiguration(
            "StreamDirectory [%s] does not exist" % stream_directory)

    return JouledConfigs(module_directory=module_directory,
                         stream_directory=stream_directory)


def parse_nilmdb_configs(nilmdb_parser, verify):
    try:
        insertion_period = int(nilmdb_parser['InsertionPeriod'])
        if (insertion_period <= 0):
            raise Exception()
        cleanup_period = int(nilmdb_parser['CleanupPeriod'])
        if (cleanup_period <= 0):
            raise Exception()
    except:
        raise InvalidConfiguration(
            "NilmdDB:InsertionPeriod/CleanupPeriod must be integer greater than 0")
    return NilmDbConfigs(url=nilmdb_parser['URL'],
                         cleanup_period=cleanup_period,
                         insertion_period=insertion_period)


def load_configs(configs={}, verify=True):
    """provide a dict INI configuration to override defaults
       if verify is True, perform checks on settings to make sure they are appropriate"""
    my_parser = configparser.ConfigParser()
    my_parser.read_dict(DEFAULT_CONFIG)
    my_parser.read_dict(configs)

    procdb_configs = parse_procdb_configs(my_parser['ProcDB'], verify)
    jouled_configs = parse_jouled_configs(my_parser['Jouled'], verify)
    nilmdb_configs = parse_nilmdb_configs(my_parser['NilmDB'], verify)
    return Configs(procdb=procdb_configs,
                   jouled=jouled_configs,
                   nilmdb=nilmdb_configs)


class ConfigManagerError(Exception):
    """Base Exception for this class"""
    pass


class InvalidConfiguration(ConfigManagerError):
    """Error parsing configuration file"""
    pass
