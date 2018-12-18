import configparser
import os
from typing import Dict
import logging

Configurations = Dict[str, configparser.ConfigParser]
logger = logging.getLogger('joule')


def load_configs(path: str) -> Configurations:
    configs: Configurations = {}
    for file in os.listdir(path):
        if not file.endswith(".conf"):
            continue
        file_path = os.path.join(path, file)
        config = configparser.ConfigParser()
        try:
            # can only happen if joule does not have read permissions
            if len(config.read(file_path)) != 1:
                logger.error("Cannot read file [%s]" % file_path)
                continue
            configs[file] = config
        except configparser.Error as e:
            logger.error("Configuration file error: %r" % e)
    return configs
