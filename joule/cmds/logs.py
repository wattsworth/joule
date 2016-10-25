
import logging
from joule.procdb import client as procdb_client
from cliff.command import Command

class LogsCmd(Command):
    "Print the logs for a module"

    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
      parser = super(LogsCmd, self).get_parser(prog_name)
      parser.add_argument('module')
      return parser
    
    def take_action(self, parsed_args):
      module_name = parsed_args.module
      module = procdb_client.find_module_by_name(module_name)
      if(module is None):
        print("No module named [%s]"%module_name)
        return
      logs = procdb_client.logs(module.id)
      if(logs is None or len(logs)==0):
        print("Log for [%s] is empty"%module_name)
        return
      for line in logs:
        print(line)

