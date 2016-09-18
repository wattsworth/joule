

import os
import configparser
from .inputmodule import InputModule
from .errors import DaemonError, ConfigError
import joule.procdb as procdb
import logging
import time

class Daemon(object):
    log = logging.getLogger(__name__)
    
    def __init__(self):
        self.input_modules = []
        

    def initialize(self,config):
        try:
            module_dir = config["Main"]["InputModuleDir"]
            for module_config in os.listdir(module_dir):
                config_path = os.path.join(module_dir,module_config)
                self._build_module(config_path)
        except KeyError as e:
            raise ConfigError(e) from e
        except FileNotFoundError as e:
            raise ConfigError("InputModuleDir [%s] does not exist"%
                              module_dir) from e

        
    def _build_module(self,module_config):
        """ create an input module from config file
        """
        config = configparser.ConfigParser()
        config.read(module_config)
        module = InputModule()
        try:
            module.initialize(config)
            procdb.client.register_input_module(module)
        except DaemonError as e:
            self.log.error("Cannot load module [%s]: %s"%(module_config,e))
            return
        self.input_modules.append(module)

    def run(self):
        for module in self.input_modules:
            module.start()
        while(True):
            for module in self.input_modules:
                module.poll()
            time.sleep(0.1)
