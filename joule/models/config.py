"""
Configuration data structure for joule
Use load_configs to retrieve Configs object
"""

import configparser
import ipaddress
import os
from joule.models import ConfigurationError

DEFAULT_CONFIG = {
    "Main":
        {
            "ModuleDirectory": "/etc/joule/module_configs",
            "StreamDirectory": "/etc/joule/stream_configs",
            "IPAddress": "127.0.0.1",
            "Port": 1234
        }
}


class JouleConfig:
    def __init__(self,
                 module_directory,
                 stream_directory,
                 ip_address,
                 port):
        self.module_directory = module_directory
        self.stream_directory = stream_directory
        self.ip_address = ip_address
        self.port = port


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

    return JouleConfig(module_directory=module_directory,
                       stream_directory=stream_directory,
                       ip_address=ip_address,
                       port=port)
