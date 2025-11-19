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

def run(path: str, db: Session) -> List[EventStream]:
    configs = load_configs(path)
    configured_streams = _parse_configs(configs)
    for path, streams in configured_streams.items():
        for stream in streams:
            stream.is_configured = True
            save_event_stream(stream, path, db)
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

def save_event_stream(new_stream: EventStream, path: str, db):
    my_folder = find_folder(path, db, create=True)
    cur_stream: EventStream = db.query(EventStream) \
        .filter_by(folder=my_folder, name=new_stream.name) \
        .one_or_none()
    if cur_stream is not None:
        cur_stream.is_configured = True
        settings_changed = cur_stream.merge_configs(new_stream)
        if settings_changed:
            cur_stream.touch()
        db.add(cur_stream)
        return
    # make sure name is unique in this destination
    data_stream_names = [s.name for s in my_folder.data_streams]
    if new_stream.name in data_stream_names:
        logger.error(f"cannot create event stream [{new_stream.name}], conflicts with existing data stream")
        return
    my_folder.event_streams.append(new_stream)
    new_stream.touch()
