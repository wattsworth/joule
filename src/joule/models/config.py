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
            "DataStreamDirectory": "/etc/joule/data_stream_configs",
            "EventStreamDirectory": "/etc/joule/event_stream_configs",
            "ImporterConfigsDirectory": "/etc/joule/importer_configs",
            "ImporterDataDirectory": "/var/joule/importer_data",
            "ExporterConfigsDirectory": "/etc/joule/exporter_configs",
            "ExporterDataDirectory": "/var/joule/exporter_data",
            "SocketDirectory": "/tmp/joule",
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
    event_directory: str
    importer_configs_directory: str
    importer_data_directory: str
    importer_inbox_directory: str
    importer_api_key: str
    exporter_configs_directory: str
    exporter_data_directory: str
    ip_address: Optional[str]
    port: Optional[int]
    socket_directory: str
    database: str
    insert_period: int
    cleanup_period: int
    max_log_lines: int
    users_file: Optional[str]
    proxies: List['Proxy']
    security: Optional['SecurityConfig']
