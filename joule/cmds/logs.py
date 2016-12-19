
from joule.procdb import client as procdb_client
from cliff.command import Command
from . import helpers

PROC_DB = "/tmp/joule-proc-db.sqlite"
NILMDB_URL = "http://localhost/nilmdb"


class LogsCmd(Command):
    "Print the logs for a module"

    def __init__(self, app, app_args, cmd_name=None):
        super(LogsCmd, self).__init__(app, app_args, cmd_name)

    def get_parser(self, prog_name):
        parser = super(LogsCmd, self).get_parser(prog_name)
        parser.add_argument('--config-file', dest="config_file")
        parser.add_argument('module')
        return parser

    def take_action(self, parsed_args):
        configs = helpers.parse_config_file(parsed_args.config_file)
        procdb = procdb_client.SQLClient(configs.procdb.db_path,
                                         configs.procdb.max_log_lines)
        module_name = parsed_args.module
        module = procdb.find_module_by_name(module_name)
        if(module is None):
            print("No module named [%s]" % module_name)
            return
        logs = procdb.find_logs_by_module(module.id)
        if(logs is None or len(logs) == 0):
            print("Log for [%s] is empty" % module_name)
            return
        for line in logs:
            print(line)
