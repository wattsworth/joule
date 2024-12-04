from sqlalchemy.orm import Session
from typing import Dict, List
import logging

from joule.models import EventStream
from joule.errors import ConfigurationError
from joule.models.folder import find as find_folder
from joule.models.event_stream import from_config as stream_from_config
from joule.services.helpers import (Configurations,
                                    load_configs)
from joule.utilities.validators import validate_stream_path
logger = logging.getLogger('joule')

Streams = Dict[str, List[EventStream]]

def run(path: str, db: Session):
    configs = load_configs(path)
    configured_streams = _parse_configs(configs)
    for path, streams in configured_streams.items():
        for stream in streams:
            _save_stream(stream, path, db)
    return [stream for _, stream in configured_streams.items()]

def _parse_configs(configs: Configurations) -> Streams:
    streams: Streams = {}
    for file_path, data in configs.items():
        try:
            s = stream_from_config(data)
            stream_path = validate_stream_path(data['Main']['path'])
            if stream_path in streams:
                streams[stream_path].append(s)
            else:
                streams[stream_path] = [s]
        except KeyError as e:
            logger.error("Invalid event stream [%s]: [Main] missing %s" %
                         (file_path, e.args[0]))
        except (ConfigurationError, ValueError) as e:
            logger.error("Invalid event stream [%s]: %s" % (file_path, e))
    return streams

def _save_stream(stream: EventStream, path: str, db):
    destination = find_folder(path, db, create=True)

    # make sure name is unique in this destination
    existing_names = [s.name for s in destination.data_streams + destination.event_streams]
    if stream.name in existing_names:
        raise ConfigurationError("stream with the same name exists in the folder")
    destination.event_streams.append(stream)
    stream.touch()
    db.commit()