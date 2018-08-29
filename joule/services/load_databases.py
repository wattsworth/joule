from typing import Dict
import logging
import configparser
from joule.models import DatabaseConfig, config
from joule.errors import ConfigurationError
from joule.services.helpers import load_configs

logger = logging.getLogger('joule')

Databases = Dict[str, DatabaseConfig]


def run(path: str) -> Databases:
    configs = load_configs(path)
    databases: Databases = {}
    for file_path, data in configs.items():
        try:
            data: configparser.ConfigParser = data["Main"]
        except KeyError:
            logger.error("Invalid database [%s]: Missing [Main] section" % file_path)
            continue
        try:
            backend = _validate_backend(data["backend"])
            name = data["name"]
            # defaults
            (port, username, password, path, url) = (0, None, None, '', '')
            if (backend == config.BACKEND.TIMESCALE or
                    backend == config.BACKEND.POSTGRES or
                    backend == config.BACKEND.NILMDB):
                url = data["url"]
                if 'username' in data:
                    username = data['username']
                if 'password' in data:
                    password = data['password']
            if backend == config.BACKEND.SQLITE:
                path = data["path"]
            databases[name] = DatabaseConfig(backend, path, url, username, password)
        except KeyError as e:
            logger.error("Invalid database [%s]: [Main] missing %s" %
                         (file_path, e.args[0]))
        except ConfigurationError as e:
            logger.error("Invalid database [%s]: %s" % (file_path, e))
    return databases


def _validate_backend(backend: str) -> config.BACKEND:
    try:
        return config.BACKEND[backend.upper()]
    except KeyError as e:
        valid_types = ", ".join([m.name.lower() for m in config.BACKEND])
        raise ConfigurationError("invalid backend [%s], choose from [%s]" %
                                 (backend, valid_types)) from e
