

import os
import configparser
from .inputmodule import InputModule
from .errors import DaemonError, ConfigError
from joule.procdb import client as procdb_client
import logging
import time

class Daemon(object):
    log = logging.getLogger(__name__)
    
    def __init__(self):
        self.input_modules = []
        

    def initialize(self,config):
        procdb_client.clear_input_modules()
        try:
            module_dir = config["Main"]["InputModuleDir"]
            for module_config in os.listdir(module_dir):
                if(not module_config.endswith(".conf")):
                    continue
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
            procdb_client.register_input_module(module)
        except (DaemonError, procdb_client.ConfigError) as e:
            self.log.error("Cannot load module [%s]: \n\t%s"%(module_config,e))
            return
        self.input_modules.append(module)

    def run(self):
        for module in self.input_modules:
            module.start()
        while(True):
            for module in self.input_modules:
                module.poll()
            time.sleep(0.1)
