from sqlalchemy.orm import Session
from typing import Dict, List
import logging
import configparser
import os
import re

from joule.models import (Stream, Folder,
                          ConfigurationError)
from joule.models.stream import from_config

logger = logging.getLogger('joule')

# types
Configurations = Dict[str, configparser.ConfigParser]
Streams = Dict[str, Stream]


def run(path: str, db: Session):
    configs = _load_configs(path)
    configured_streams = _parse_configs(configs)
    root = db.query(Folder).filter_by(parent=None).one()
    for path, stream in configured_streams.items():
        _save_stream(stream, path, root, db)
    db.commit()


def _load_configs(path: str) -> Configurations:
    configs: Configurations = {}
    for file in os.listdir(path):
        if not file.endswith(".conf"):
            continue
        file_path = os.path.join(path, file)
        config = configparser.ConfigParser()
        try:
            if len(config.read(file_path)) != 1:
                logger.error("Cannot read file [%s]" % file_path)
                continue
            configs[file] = config
        except configparser.Error as e:
            logger.error(e)
    return configs


def _parse_configs(configs: Configurations) -> Streams:
    streams: Streams = {}
    for path, data in configs.items():
        try:
            s = from_config(data)
            stream_path = _validate_path(data['Main']['path'])
            streams[stream_path] = s
        except KeyError as e:
            logger.error("Invalid stream [%s]: [Main] missing %s" %
                         (path, e.args[0]))
        except ConfigurationError as e:
            logger.error("Invalid stream [%s]: %s" % (path, e))
    return streams


def _validate_path(path: str) -> str:
    #
    if path != '/' and re.fullmatch('^(/[\w -]+)+$', path) is None:
        raise ConfigurationError(
            "invalid path, use format: /dir/subdir/../file. "
            "valid characters: [0-9,A-Z,a-z,_,-, ]")

    return path


def _save_stream(new_stream: Stream, path: str, root: Folder, db: Session) -> None:
    path_chunks = list(reversed(path.split('/')[1:]))
    folder = _find_or_create_folder(path_chunks, root, db)
    cur_stream: Stream = db.query(Stream) \
        .filter_by(folder=folder, name=new_stream.name) \
        .one_or_none()
    if cur_stream is not None:
        if cur_stream.layout != new_stream.layout:
            logger.error("Invalid layout %s for [%s/%s], existing stream has layout %s" % (
                new_stream.layout, cur_stream.path, cur_stream.name, cur_stream.layout))
        else:
            cur_stream.merge_configs(new_stream)
            db.add(cur_stream)
            db.expunge(new_stream)
    else:
        folder.streams.append(new_stream)


def _find_or_create_folder(path_chunks: List[str], parent: Folder, db: Session) -> Folder:
    assert(parent is not None)
    if len(path_chunks) == 0:
        return parent
    name = path_chunks.pop()
    folder = db.query(Folder).filter_by(parent=parent, name=name).one_or_none()
    if folder is None:
        folder = Folder(name=name)
        parent.children.append(folder)
    return _find_or_create_folder(path_chunks, folder, db)
