from sqlalchemy.orm import Session
from typing import List, TYPE_CHECKING
import logging

from joule.models import (Module, Stream,
                          Element, Pipe,
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
Pipes = List[Pipe]


def run(path: str, db: Session):
    configs = load_configs(path)
    configured_modules = _parse_configs(configs, db)
    for module in configured_modules:
        db.add(module)
    return configured_modules


def _parse_configs(configs: Configurations, db: Session) -> Modules:
    stage1_modules: List[(Module, ConfigParser, str)] = []
    # Pass 1: parse module parameters
    for file_path, config in configs.items():
        try:
            module = module_from_config(config)
            module.locked = True
            stage1_modules.append((module, config, file_path))
        except ConfigurationError as e:
            logger.error("Invalid module [%s]: %s" % (file_path, e))
    # Pass 2: parse outputs
    stage2_modules: List[(Module, ConfigParser, str)] = []
    for module, config, file_path in stage1_modules:
        try:
            module.pipes = _find_outputs(config, db)
            stage2_modules.append((module, config, file_path))
        except ConfigurationError as e:
            logger.error("Invalid module [%s]: %s" % (file_path, e))
    # Pass 3: parse inputs
    parsed_modules: Modules = []
    for module, config, file_path in stage2_modules:
        try:
            module.pipes += _find_inputs(config, db)
            parsed_modules.append(module)
        except ConfigurationError as e:
            logger.error("Invalid module [%s]: %s" % (file_path, e))
    return parsed_modules


def _find_outputs(config: 'ConfigParser', db: Session) -> Pipes:
    outputs = []
    if 'Outputs' not in config:
        raise ConfigurationError("Missing section [Outputs]")
    for name, pipe_config in config['Outputs'].items():
        try:
            my_stream = _stream_from_pipe_config(pipe_config, db)
            outputs.append(Pipe(name=name, stream=my_stream,
                                direction=Pipe.DIRECTION.OUTPUT))
        except ConfigurationError as e:
            raise ConfigurationError("Output [%s=%s]: %s" %
                                     (name, pipe_config, e))
    return outputs


def _find_inputs(config: 'ConfigParser', db: Session) -> Pipes:
    inputs = []
    if 'Inputs' not in config:
        raise ConfigurationError("Missing section [Inputs]")
    for name, pipe_config in config['Inputs'].items():
        try:
            my_stream = _stream_from_pipe_config(pipe_config, db)
            inputs.append(Pipe(name=name, stream=my_stream,
                               direction=Pipe.DIRECTION.INPUT))
        except ConfigurationError as e:
            raise ConfigurationError("Input [%s=%s]: %s" %
                                     (name, pipe_config, e))
    return inputs


# basic format of stream is just the full_path
# /file/path/stream_name
# but streams may be configured inline
# /file/path/stream_name:datatype[e1, e2, e3, ...]
#  where e1, e2, e2, ... are the element names
#
def _stream_from_pipe_config(pipe_config: str, db: Session) -> Stream:
    # separate the configuration pieces
    (path, name, inline_config) = _parse_pipe_config(pipe_config)
    if path is None or name is None:
        raise ConfigurationError("invalid configuration [%s]" % pipe_config)
    name = stream.validate_name(name)
    # parse the inline configuration
    (datatype, element_names) = _parse_inline_config(inline_config)
    my_folder = folder.find_or_create(path, db)
    # check if the stream exists in the database
    existing_stream = db.query(Stream). \
        filter_by(folder=my_folder, name=name). \
        one_or_none()
    if existing_stream is not None:
        if len(inline_config) > 0:
            _validate_config_match(existing_stream, datatype, element_names)
        return existing_stream
    # if the stream doesn't exist it *must* have inline configuration
    if len(inline_config) == 0:
        raise ConfigurationError("no stream configuration for [%s]" % pipe_config)
    # build the stream from inline config
    my_stream = stream.Stream(name=name,
                              datatype=datatype)
    i = 0
    for e in element_names:
        my_stream.elements.append(Element(name=e, index=i))
        i += 1
    my_folder.streams.append(my_stream)
    db.add(my_stream)
    return my_stream


def _parse_pipe_config(pipe_config: str) -> (str, str, str):
    # convert /path/name:datatype[e0,e1,e2] into (/path, name, datatype[e0,e1,e2])
    if ':' in pipe_config:
        full_path = pipe_config.split(':')[0]
        inline_config = pipe_config.split(':')[1]
    else:
        full_path = pipe_config
        inline_config = ""
    if '/' not in full_path:
        raise ConfigurationError("invalid path [%s]" % pipe_config)
    path_chunks = full_path.split('/')
    name = path_chunks.pop()
    if name == "":
        raise ConfigurationError("invalid stream name [%s]" % pipe_config)
    path = '/'.join(path_chunks)
    return path, name, inline_config


def _parse_inline_config(inline_config: str) -> (Stream.DATATYPE, List[str]):
    if len(inline_config) == 0:
        return None, None
    try:
        config = inline_config.split('[')
        if len(config) != 2:
            raise ConfigurationError("format is datatype[e1,e2,e3,...]")
        datatype = stream.validate_datatype(config[0].strip())
        element_names = [e.strip() for e in config[1].strip()[:-1].split(",")]
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
                                 (existing_stream.name,
                                  existing_stream.datatype))

    # verify elem_names
    existing_names = [e.name for e in existing_stream.elements]
    if len(existing_names) != len(elem_names):
        raise ConfigurationError("Stream exists with different elements")
    for name in elem_names:
        if name not in existing_names:
            raise ConfigurationError("Stream exists with different elements")
