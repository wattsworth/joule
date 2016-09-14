

import os
import configparser
from .inputmodule import InputModule
from .errors import DaemonError, ConfigError
import logging
import time

class Daemon(object):
    log = logging.getLogger(__name__)
    
    def __init__(self):
        self.input_modules = []
        

    def initialize(self,config):
        try:
            module_dir = config.get("Main","InputModuleDir")
            for module_config in os.listdir(module_dir):
                config_path = os.path.join(module_dir,module_config)
                self.__build_module(config_path)
        except configparser.NoSectionError as e:
            raise ConfigError(e) from e
        except FileNotFoundError as e:
            raise ConfigError("InputModuleDir [%s] does not exist"%
                              module_dir) from e

    def __build_module(self,module_config):
        """ create an input module from config file
        """
        config = configparser.ConfigParser()
        config.read(module_config)
        module = InputModule()
        try:
            module.initialize(config)
        except DaemonError as e:
            self.log.error("Cannot initialize module [%s]: %s"%(module_config,e))
        self.input_modules.append(module)

    def run(self):
        for module in self.input_modules:
            module.start()
        while(True):
            for module in self.input_modules:
                module.poll()
            time.sleep(0.1)
