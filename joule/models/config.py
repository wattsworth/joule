"""
Configuration data structure for joule
Use load_configs to retrieve Configs object
"""

import configparser
import ipaddress
import os
import enum
from joule.models import ConfigurationError

DEFAULT_CONFIG = {
    "Main":
        {
            "ModuleDirectory": "/etc/joule/module_configs",
            "StreamDirectory": "/etc/joule/stream_configs",
            "IPAddress": "127.0.0.1",
            "Port": 1234
        },
    "DataStore":
        {
            "Type": "nilmdb",
            "URL": "http://localhost/nilmdb",
            "InsertPeriod": "5",
            "CleanupPeriod": "60"
        }
}


class DATASTORE(enum.Enum):
    NILMDB = enum.auto()
    TIMESCALE = enum.auto()
    SQL = enum.auto()


class DataStoreConfig:
    def __init__(self, store_type: DATASTORE,
                 url: str, insert_period: float, cleanup_period: float):
        self.store_type = store_type
        self.url = url
        self.insert_period = insert_period
        self.cleanup_period = cleanup_period


class JouleConfig:
    def __init__(self,
                 module_directory: str,
                 stream_directory: str,
                 ip_address: str,
                 port: int,
                 data_store: DataStoreConfig):
        self.module_directory = module_directory
        self.stream_directory = stream_directory
        self.ip_address = ip_address
        self.port = port
        self.data_store = data_store


def build(custom_values, verify=True) -> JouleConfig:
    """provide a dict INI configuration to override defaults
       if verify is True, perform checks on settings to make sure they are appropriate"""
    my_configs = configparser.ConfigParser()
    my_configs.read_dict(DEFAULT_CONFIG)
    if custom_values is not None:
        my_configs.read_dict(custom_values)

    # ModuleDirectory
    module_directory = my_configs['Main']['ModuleDirectory']
    if not os.path.isdir(module_directory) and verify:
        raise ConfigurationError(
            "ModuleDirectory [%s] does not exist" % module_directory)
    # StreamDirectory
    stream_directory = my_configs['Main']['StreamDirectory']
    if not os.path.isdir(stream_directory) and verify:
        raise ConfigurationError(
            "StreamDirectory [%s] does not exist" % stream_directory)
    # IPAddress
    ip_address = my_configs['Main']['IPAddress']
    try:
        ipaddress.ip_address(ip_address)
    except ValueError as e:
        raise ConfigurationError("IPAddress is invalid") from e
    # Port
    try:
        port = int(my_configs['Main']['Port'])
        if port < 0 or port > 65535:
            raise ValueError()
    except ValueError as e:
        raise ConfigurationError("Jouled:Port must be between 0 - 65535") from e

    # DataStore:Type
    store_configs = my_configs['DataStore']
    configured_store_type = store_configs['Type']
    if configured_store_type.lower() == 'nilmdb':
        data_store_type = DATASTORE.NILMDB
    elif configured_store_type.lower() == 'timescale':
        data_store_type = DATASTORE.TIMESCALE
    elif configured_store_type.lower() == 'sql':
        data_store_type = DATASTORE.SQL
    else:
        raise ConfigurationError("Unknown data store type [%s]" % configured_store_type)

    # DataStore:URL
    url = store_configs['url']

    # DataStore:InsertPeriod
    try:
        insert_period = int(store_configs['InsertPeriod'])
        if insert_period <= 0:
            raise ValueError()
    except ValueError:
        raise ConfigurationError("DataStore:InsertPeriod must be a postive number")

    # DataStore:CleanupPeriod
    try:
        cleanup_period = int(store_configs['InsertPeriod'])
        if cleanup_period <= 0 or cleanup_period < insert_period:
            raise ValueError()
    except ValueError:
        raise ConfigurationError("DataStore:InsertPeriod must be a postive number > InsertPeriod")

    data_store = DataStoreConfig(data_store_type, url, insert_period, cleanup_period)
    return JouleConfig(module_directory=module_directory,
                       stream_directory=stream_directory,
                       ip_address=ip_address,
                       port=port,
                       data_store=data_store)
