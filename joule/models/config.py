"""
Configuration data structure for joule
Use load_configs to retrieve Configs object
"""

import enum
from joule.models import Proxy
from typing import Optional, List
import ssl

DEFAULT_CONFIG = {
    "Main":
        {
            "Name": "joule_node",
            "ModuleDirectory": "/etc/joule/module_configs",
            "StreamDirectory": "/etc/joule/stream_configs",
            "IPAddress": "127.0.0.1",
            "Port": 8088,
            "Database": "joule@localhost:5438/joule",
            "InsertPeriod": 5,
            "CleanupPeriod": 60,
            "MaxLogLines": 100,
            "NilmdbUrl": '',
        },
    "Proxies": {}
}


class SecurityConfig:
    def __init__(self,
                 certfile: str,
                 keyfile: str,
                 cafile: str):
        self.certfile = certfile
        self.keyfile = keyfile
        self.cafile = cafile


class JouleConfig:
    def __init__(self,
                 name: str,
                 module_directory: str,
                 stream_directory: str,
                 ip_address: str,
                 port: int,
                 database: str,
                 insert_period: int,
                 cleanup_period: int,
                 max_log_lines: int,
                 nilmdb_url: Optional[str],
                 proxies: List[Proxy],
                 security: Optional[SecurityConfig]):
        self.name = name
        self.module_directory = module_directory
        self.stream_directory = stream_directory
        self.ip_address = ip_address
        self.port = port
        self.database = database
        self.insert_period = insert_period
        self.cleanup_period = cleanup_period
        self.max_log_lings = max_log_lines
        self.nilmdb_url = nilmdb_url
        self.proxies = proxies
        self.security = security
