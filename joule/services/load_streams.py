from sqlalchemy.orm import Session
from typing import Dict ,List
import logging
import re

from joule.models import Stream
from joule.errors import ConfigurationError
from joule.models.folder import find as find_folder
from joule.models.stream import from_config as stream_from_config
from joule.services.helpers import (Configurations,
                                    load_configs)

logger = logging.getLogger('joule')

# types
Streams = Dict[str, List[Stream]]


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
            s.is_configured = True
            stream_path = _validate_path(data['Main']['path'])
            if stream_path in streams:
                streams[stream_path].append(s)
            else:
                streams[stream_path] = [s]
        except KeyError as e:
            logger.error("Invalid stream [%s]: [Main] missing %s" %
                         (file_path, e.args[0]))
        except ConfigurationError as e:
            logger.error("Invalid stream [%s]: %s" % (file_path, e))
    return streams


def _validate_path(path: str) -> str:
    #
    if path != '/' and re.fullmatch(r'^(/[\w -]+)+$', path) is None:
        raise ConfigurationError(
            "invalid path, use format: /dir/subdir/../file. "
            "valid characters: [0-9,A-Z,a-z,_,-, ]")

    return path


def _save_stream(new_stream: Stream, path: str, db: Session) -> None:
    my_folder = find_folder(path, db, create=True)
    cur_stream: Stream = db.query(Stream) \
        .filter_by(folder=my_folder, name=new_stream.name) \
        .one_or_none()
    if cur_stream is not None:
        if cur_stream.layout != new_stream.layout:
            logger.error("Invalid layout %s for [%s], existing stream has layout %s" % (
                new_stream.layout, cur_stream.name, cur_stream.layout))
        else:
            cur_stream.merge_configs(new_stream)
            db.add(cur_stream)
            db.expunge(new_stream)
    else:
        my_folder.streams.append(new_stream)
