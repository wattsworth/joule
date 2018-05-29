from sqlalchemy.orm import Session
from typing import List, TYPE_CHECKING
import re
import logging

from joule.models import (Module, Stream,
                          Element,
                          ConfigurationError,
                          stream, folder)
from joule.models.module import from_config as module_from_config

from joule.services.helpers import (load_configs,
                                    Configurations)

if TYPE_CHECKING:
    from configparser import ConfigParser

logger = logging.getLogger('joule')

# types
Modules = List[Module]
Streams = List[Stream]


def run(path: str, db: Session):
    configs = load_configs(path)
    configured_modules = _parse_configs(configs, db)
    # first connect all outputs
    # then connect all inputs
    for module in configured_modules:
        db.add(module)


def _parse_configs(configs: Configurations, db: Session) -> Modules:
    stage1_modules: List[(Module, ConfigParser, str)] = []
    # Pass 1: parse module parameters
    for file_path, config in configs.items():
        try:
            m = module_from_config(config)
            m.locked = True
            stage1_modules.append((m, config, file_path))
        except ConfigurationError as e:
            logger.error("Invalid module [%s]: %s" % (file_path, e))
    # Pass 2: parse inputs
    stage2_modules: List[(Module, ConfigParser, str)] = []
    for module, config, file_path in stage1_modules:
        try:
            module.inputs = _find_inputs(config, db)
            stage2_modules.append((module, config, file_path))
        except ConfigurationError as e:
            logger.error("Invalid module [%s]: %s" % (file_path, e))
    # Pass 3: parse outputs
    parsed_modules: Modules = []
    for module, config, file_path in stage2_modules:
        try:
            module.outputs = _find_outputs(config, db)
            parsed_modules.append(module)
        except ConfigurationError as e:
            logger.error("Invalid module [%s]: %s" % (file_path, e))
    return parsed_modules


def _find_inputs(config: ConfigParser, db: Session) -> Streams:
    inputs = []
    if 'Inputs' not in config:
        raise ConfigurationError("Missing section [Inputs]")
    for name, path_config in config['Inputs'].items():
        try:
            inputs.append(_stream_from_path_config(path_config, db))
        except ConfigurationError as e:
            raise ConfigurationError("Input [%s=%s]: %s" %
                                     (name, path_config, e))
    return inputs


def _find_outputs(config: ConfigParser, db: Session) -> Streams:
    outputs = []
    if 'Outputs' not in config:
        raise ConfigurationError("Missing section [Outputs]")
    for name, path_config in config['Inputs'].items():
        try:
            outputs.append(_stream_from_path_config(path_config, db))
        except ConfigurationError as e:
            raise ConfigurationError("Output [%s=%s]: %s" %
                                     (name, path_config, e))
    return outputs


# basic format of stream is just the full_path
# /file/path/stream_name
# but streams may be configured inline
# /file/path/stream_name:datatype[e1, e2, e3, ...]
#  where e1, e2, e2, ... are the element names
#
def _stream_from_path_config(path_config, db):
    # separate the configuration pieces
    (path, name, inline_config) = re.match("/TODO/", path_config)
    if path is None or name is None:
        raise ConfigurationError("invalid configuration [%s]" % path_config)
    name = stream.validate_name(name)
    # parse the inline configuration
    (datatype, element_names) = _parse_inline_config(inline_config)
    my_folder = folder.find_or_create(path, db)
    # check if the stream exists in the database
    existing_stream = db.query(Stream). \
        filter_by(folder=my_folder, name=name)
    if existing_stream is not None and len(inline_config) > 0:
        _validate_config_match(existing_stream, datatype, element_names)
        return existing_stream
    # if the stream doesn't exist it *must* have inline configuration
    if inline_config is None:
        raise ConfigurationError("no stream configuration for [%s]" % path_config)
    # build the stream from inline config
    my_stream = stream.Stream(name=name,
                              datatype=datatype)
    for e in element_names:
        my_stream.elements.append(Element(name=e))
    my_folder.streams.append(my_stream)
    db.add(my_stream)
    return my_stream


def _parse_inline_config(inline_config: str) -> (Stream.DATATYPE, List[str]):
    if len(inline_config) == 0:
        return None, None
    try:
        config = inline_config.split(':')
        if len(config) != 2:
            raise ConfigurationError("format is datatype:[e1,e2,e3,...]")
        datatype = stream.validate_datatype(config[0])
        element_names = [e.rstrip().lstrip() for e in config[1][1:-1].split(",")]
        return datatype, element_names
    except ConfigurationError as e:
        raise ConfigurationError("invalid inline configuration") from e


def _validate_config_match(existing_stream: Stream,
                           datatype: Stream.DATATYPE,
                           elem_names: List[str]):
    # verify data_type match if specified
    if (datatype is not None and
            datatype != existing_stream.datatype):
        raise ConfigurationError("Stream [%s] exists with data_type %s" %
                                 (existing_stream.full_path,
                                  existing_stream.datatype))

    # verify elem_names
    existing_names = [e.name for e in existing_stream.elements]
    if len(existing_names) != len(elem_names):
        raise ConfigurationError("Stream [%s] exists with different elements" %
                                 existing_stream.full_path)
    for name in elem_names:
        if name not in existing_names:
            raise ConfigurationError("Stream [%s] exists with different elements" %
                                     existing_stream.full_path)
