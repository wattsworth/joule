import configparser
import os
from typing import Dict
import logging
import shutil

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

def flush_directory(path: str) -> None:
    """Remove the contents of a directory: all files, symlinks, and subdirectories"""
    for item in os.listdir(path):
        item_path = os.path.join(path, item)
        if os.path.isfile(item_path) or os.path.islink(item_path):
            os.unlink(item_path)  # Remove file or symbolic link
        elif os.path.isdir(item_path):
            shutil.rmtree(item_path)  # Remove directory and its contents