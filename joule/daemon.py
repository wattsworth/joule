import logging
import pdb
from cliff.command import Command
import argparse

class DaemonCmd(Command):
    "The Joule Daemon"

    log = logging.getLogger(__name__)
    def __init__(self, app, app_args, cmd_name=None):
        super(DaemonCmd, self).__init__(app,app_args,cmd_name)
        self.daemon = Daemon()
        
    def get_parser(self, prog_name):
        parser = super(DaemonCmd, self).get_parser(prog_name)
        return self.daemon.setup_parser(parser)
    
    
    def take_action(self, parsed_args):
        self.daemon.run(parsed_args)
        
class Daemon(object):
    def __init__(self):
        pass
    
    def setup_parser(self, parser):
        parser.add_argument("--config",default="")
        return parser

    def run(self,parsed_args):
        print ("config: %s"%parsed_args.config)
        
def main():
    parser = argparse.ArgumentParser()
    daemon = Daemon()
    daemon.setup_parser(parser)
    args = parser.parse_args()
    daemon.run(args)

if __name__ == "__main__":
    main()
