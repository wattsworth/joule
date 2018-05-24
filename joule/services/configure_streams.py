from sqlalchemy.orm import Session
from typing import Dict, List
import logging
import configparser
import os
import pdb

from joule.models import (stream, Stream, Folder,
                          ConfigurationError)

logger = logging.getLogger('joule')

# types
Configurations = Dict[str, configparser.ConfigParser]
Streams = List[Stream]


def run(path: str, db: Session):
    configs = _load_configs(path)
    configured_streams = _parse_configs(configs)
    _update_db(configured_streams, db)


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
    streams: Streams = []
    for path, data in configs.items():
        try:
            s = stream.from_config(data)
            streams.append(s)
        except ConfigurationError as e:
            logger.error("Invalid stream [%s]: %s" % (path, e))
    return streams


def _update_db(streams: Streams, db: Session) -> None:
    # check if the stream is already in the database
    for new_stream in streams:
        cur_stream: Stream = db.query(Stream) \
            .filter_by(path=new_stream.path) \
            .filter_by(name=new_stream.name)\
            .first()
        if cur_stream is not None:
            if cur_stream.layout != new_stream.layout:
                logger.error("Invalid layout %s for [%s/%s], existing stream has layout %s" % (
                    new_stream.layout, cur_stream.path, cur_stream.name, cur_stream.layout))
            else:
                cur_stream.merge_configs(new_stream)
                db.add(cur_stream)
                db.expunge(new_stream)
        else:
            folders = new_stream.path.split("/")
            #cur_folder = db.query(Folder).filter_by(path="/")
            #for f in folders:
            #    if cur_folder.children.filter_by(name=f).none?
            #    cur_folder.children.append(Folder(name=f))
            db.add(new_stream)
    db.commit()
