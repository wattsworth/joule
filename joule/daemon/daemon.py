

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
            module_dir = config["Main"]["InputModuleDir"]
            for module_config in os.listdir(module_dir):
                config_path = os.path.join(module_dir,module_config)
                self.__build_module(config_path)
        except KeyError as e:
            raise ConfigError(e) from e
        except FileNotFoundError as e:
            raise ConfigError("InputModuleDir [%s] does not exist"%
                              module_dir) from e
        #all modules loaded, let the proc_db know
        self.proc_db.set_input_modules(self.input_modules)
        
    def __build_module(self,module_config):
        """ create an input module from config file
        """
        config = configparser.ConfigParser()
        config.read(module_config)
        module = InputModule()
        try:
            module.initialize(config)
        except DaemonError as e:
            self.log.error("Cannot load module [%s]: %s"%(module_config,e))
            return
        #2.) create a database path if necessary
        #3.) make sure path is unique
        #everything checks out,
        self.input_modules.append(module)

    def run(self):
        for module in self.input_modules:
            module.start()
        while(True):
            for module in self.input_modules:
                module.poll()
            time.sleep(0.1)
