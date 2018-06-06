from sqlalchemy.orm import Session
from typing import List, TYPE_CHECKING
import logging
import os
import asyncio

from joule.models import (Module, pipes,
                          ConfigurationError)
from joule.models.module import from_config as module_from_config

from joule.services import parse_pipe_config
from joule.services.helpers import (load_configs,
                                    Configurations)

if TYPE_CHECKING:
    from configparser import ConfigParser

logger = logging.getLogger('joule')

# types
Modules = List[Module]
InputPipes = List[pipes.InputPipe]
OutputPipes = List[pipes.OutputPipe]
Loop = asyncio.AbstractEventLoop


def run(path: str, db: Session, loop: Loop) -> Modules:
    configs = load_configs(path)
    return _parse_configs(configs, db, loop)


def _parse_configs(configs: Configurations, db: Session, loop: Loop) -> Modules:
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
            module.outputs = _connect_outputs(config, db, loop)
            stage2_modules.append((module, config, file_path))
        except ConfigurationError as e:
            logger.error("Invalid module [%s]: %s" % (file_path, e))
    # Pass 3: parse inputs
    parsed_modules: Modules = []
    for module, config, file_path in stage2_modules:
        try:
            module.inputs = _connect_inputs(config, db, loop)
            parsed_modules.append(module)
        except ConfigurationError as e:
            logger.error("Invalid module [%s]: %s" % (file_path, e))
    return parsed_modules


def _connect_outputs(config: 'ConfigParser', db: Session, loop: Loop) -> InputPipes:
    outputs = []
    if 'Outputs' not in config:
        raise ConfigurationError("Missing section [Outputs]")
    for name, pipe_config in config['Outputs'].items():
        try:
            my_stream = parse_pipe_config.run(pipe_config, db)
            (r, w) = os.pipe()
            rf = pipes.reader_factory(r, loop)
            os.set_inheritable(w, True)
            # create an input pipe to read the module output
            outputs.append(pipes.InputPipe(name=name, fd=w,
                                           stream=my_stream,
                                           reader_factory=rf))
        except ConfigurationError as e:
            raise ConfigurationError("Output [%s=%s]: %s" %
                                     (name, pipe_config, e))
    return outputs


def _connect_inputs(config: 'ConfigParser', db: Session, loop: Loop) -> OutputPipes:
    inputs = []
    if 'Inputs' not in config:
        raise ConfigurationError("Missing section [Inputs]")
    for name, pipe_config in config['Inputs'].items():
        try:
            my_stream = parse_pipe_config.run(pipe_config, db)
            (r, w) = os.pipe()
            wf = pipes.writer_factory(w, loop)
            os.set_inheritable(r, True)
            # create an output pipe to provide the module input
            inputs.append(pipes.OutputPipe(name=name, fd=r,
                                           stream=my_stream,
                                           writer_factory=wf))
        except ConfigurationError as e:
            raise ConfigurationError("Input [%s=%s]: %s" %
                                     (name, pipe_config, e))
    return inputs
