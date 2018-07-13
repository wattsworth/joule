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
            "DatabaseDirectory": "/etc/joule/database_configs",
            "IPAddress": "127.0.0.1",
            "Port": 3000,
            "Database": "default"
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


class DATABASE(enum.Enum):
    POSTGRES = enum.auto()
    SQLITE = enum.auto()


class DatabaseConfig:
    def __init__(self, backend: DATABASE,
                 path: str = "",
                 url: str = "",
                 port: int = 0,
                 username: str = "",
                 password: str = "", ):
        self.url = url
        self.port = port
        self.path = path
        self.username = username
        self.password = password
        self.backend = backend


class DataStoreConfig:
    def __init__(self, backend: DATASTORE,
                 insert_period: float, cleanup_period: float,
                 url: str = "", database_name: str = ""):
        self.backend = backend
        self.url = url  # for NilmDB
        self.insert_period = insert_period
        self.database_name = database_name  # for Timescale
        self.cleanup_period = cleanup_period


class JouleConfig:
    def __init__(self,
                 module_directory: str,
                 stream_directory: str,
                 database_directory: str,
                 ip_address: str,
                 port: int,
                 database_name: str,
                 data_store: DataStoreConfig):
        self.module_directory = module_directory
        self.stream_directory = stream_directory
        self.database_directory = database_directory
        self.ip_address = ip_address
        self.port = port
        self.database_name = database_name
        self.data_store = data_store

