from sqlalchemy.orm import session
from typing import Dict, List
import logging
import configparser
import os

from joule.models import stream, ConfigurationError

logger = logging.getLogger('joule')

# types
Configurations = Dict[str, configparser.ConfigParser]
Streams = List[stream.Stream]


def run(path: str, db: session):
    configs = _load_configs(path)
    configured_streams = _parse_configs(configs)
    streams = _merge_streams(configured_streams, db.find_streams)
    db.add(streams)


def _load_configs(path: str) -> Configurations:
    configs: Configurations = {}
    for file in os.listdir(path):
        if not file.endswith(".conf"):
            continue
        path = os.path.join(path, file)
        config = configparser.ConfigParser()
        configs[file] = config.read(path)
    return configs


def _parse_configs(configs: Configurations) -> Streams:
    streams: Streams = []
    for path, data in configs:
        try:
            s = stream.from_config(data)
            streams.append(s)
        except ConfigurationError as e:
            logger.error("Cannot load [%s]: %s" % (path, e))
    return streams


def _merge_streams(configured_streams: Streams,
                   db_streams: Streams) -> Streams:
    pass
    # todo
