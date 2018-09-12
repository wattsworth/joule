from sqlalchemy.orm import Session
from typing import List, Dict, TYPE_CHECKING
import logging

from joule.models import (Module, Stream)
from joule.errors import ConfigurationError
from joule.models.module import from_config as module_from_config

from joule.services import parse_pipe_config
from joule.services.helpers import (load_configs,
                                    Configurations)

if TYPE_CHECKING:
    from configparser import ConfigParser

logger = logging.getLogger('joule')

# types
Modules = List[Module]
StreamConnections = Dict[str, Stream]


def run(path: str, db: Session) -> Modules:
    configs = load_configs(path)
    return _parse_configs(configs, db)


def _parse_configs(configs: Configurations, db: Session) -> Modules:
    stage1_modules: List[(Module, ConfigParser, str)] = []
    # Pass 1: parse module parameters
    uuid = 0
    for file_path, config in configs.items():
        try:
            module = module_from_config(config)
            module.uuid = uuid
            stage1_modules.append((module, config, file_path))
            uuid += 1
        except ConfigurationError as e:
            logger.error("Invalid module [%s]: %s" % (file_path, e))
    # Pass 2: parse outputs
    stage2_modules: List[(Module, ConfigParser, str)] = []
    for module, config, file_path in stage1_modules:
        try:
            module.outputs = _connect_outputs(config, db)
            stage2_modules.append((module, config, file_path))
        except ConfigurationError as e:
            logger.error("Invalid module [%s]: %s" % (file_path, e))
    # Pass 3: parse inputs
    parsed_modules: Modules = []
    for module, config, file_path in stage2_modules:
        try:
            module.inputs = _connect_inputs(config, db)
            parsed_modules.append(module)
        except ConfigurationError as e:
            logger.error("Invalid module [%s]: %s" % (file_path, e))
    # Designate active streams
    for module in parsed_modules:
        for stream in module.outputs.values():
            stream.is_destination = True
        for stream in module.inputs.values():
            stream.is_source = True
    return parsed_modules


def _connect_outputs(config: 'ConfigParser', db: Session) -> StreamConnections:
    outputs: StreamConnections = {}
    if 'Outputs' not in config:
        return outputs
    for name, pipe_config in config['Outputs'].items():
        try:
            outputs[name] = parse_pipe_config.run(pipe_config, db)
        except ConfigurationError as e:
            raise ConfigurationError("Output [%s=%s]: %s" %
                                     (name, pipe_config, e))
    return outputs


def _connect_inputs(config: 'ConfigParser', db: Session) -> StreamConnections:
    inputs: StreamConnections = {}
    if 'Inputs' not in config:
        return inputs
    for name, pipe_config in config['Inputs'].items():
        try:
            inputs[name] = parse_pipe_config.run(pipe_config, db)
        except ConfigurationError as e:
            raise ConfigurationError("Input [%s=%s]: %s" %
                                     (name, pipe_config, e))
    return inputs
