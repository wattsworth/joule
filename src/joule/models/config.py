"""
Configuration data structure for joule
Use load_configs to retrieve Configs object
"""

from joule.models import Proxy
from typing import Optional, List
from dataclasses import dataclass

DEFAULT_CONFIG = {
    "Main":
        {
            "Name": "joule_node",
            "ModuleDirectory": "/etc/joule/module_configs",
            "StreamDirectory": "/etc/joule/stream_configs",
            "SocketDirectory": "/tmp/joule",
            #"Database": "joule@localhost:5432/joule",
            "InsertPeriod": 5,
            "CleanupPeriod": 60,
            "MaxLogLines": 100,
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

@dataclass
class JouleConfig:
    name: str
    module_directory: str
    stream_directory: str
    ip_address: Optional[str]
    port: Optional[int]
    socket_directory: str
    database: str
    insert_period: int
    cleanup_period: int
    max_log_lines: int
    nilmdb_url: Optional[str]
    users_file: Optional[str]
    proxies: List['Proxy']
    security: Optional['SecurityConfig']
