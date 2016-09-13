import logging
from .daemon import Daemon
from cliff.command import Command
import configparser

class DaemonCmd(Command):
    "The Joule Daemon"

    log = logging.getLogger(__name__)
    def __init__(self, app, app_args, cmd_name=None):
        super(DaemonCmd, self).__init__(app,app_args,cmd_name)
        self.daemon = Daemon()
        
    def get_parser(self, prog_name):
        parser = super(DaemonCmd, self).get_parser(prog_name)
        parser.add_argument("--config",default="")
        return parser
    
    
    def take_action(self, parsed_args):
        config = configparser.ConfigParser()
        config.read(parsed_args.config)
        self.daemon.initialize(configs)
        
