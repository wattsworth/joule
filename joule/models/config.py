"""
Configuration data structure for joule
Use load_configs to retrieve Configs object
"""

import enum
from joule.errors import ConfigurationError

DEFAULT_CONFIG = {
    "Main":
        {
            "ModuleDirectory": "/etc/joule/module_configs",
            "StreamDirectory": "/etc/joule/stream_configs",
            "DatabaseDirectory": "/etc/joule/database_configs",
            "IPAddress": "127.0.0.1",
            "Port": 3000,
            "Database": "metadata"  # may not be NILMDB
        },
    "DataStore":
        {
            "Database": "datastore",  # must be NILMDB or TIMESCALE
            "InsertPeriod": "5",
            "CleanupPeriod": "60"
        }
}


class BACKEND(enum.Enum):
    NILMDB = enum.auto()
    POSTGRES = enum.auto()
    SQLITE = enum.auto()
    TIMESCALE = enum.auto()


class DatabaseConfig:
    def __init__(self, backend: BACKEND,
                 path: str = "",
                 url: str = "",
                 username: str = "",
                 password: str = "", ):
        self.url = url
        self.path = path
        self.username = username
        self.password = password
        self.backend = backend

    @property
    def engine_config(self):
        if self.backend == BACKEND.SQLITE:
            return "sqlite:///%s" % self.path
        elif (self.backend == BACKEND.POSTGRES or
              self.backend == BACKEND.TIMESCALE):
            return "postgresql://%s:%s@%s" % (self.username, self.password, self.url)
        else:
            raise ConfigurationError("no sqlalchemy support for %s" % self.backend.value)


class DataStoreConfig:
    def __init__(self,
                 insert_period: float, cleanup_period: float,
                 database_name: str = ""):
        self.insert_period = insert_period
        self.database_name = database_name
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
