
from cliff.command import Command
from . import helpers

class DocsCmd(Command):
    "Manage the Joule Module documentation repository"

    def __init__(self, app, app_args, cmd_name=None):
        super(LogsCmd, self).__init__(app, app_args, cmd_name)

    def get_parser(self, prog_name):
        parser = super(LogsCmd, self).get_parser(prog_name)
        parser.add_argument('--config-file', dest="config_file")
        parser.add_argument('module')
        return parser

    def take_action(self, parsed_args):
        configs = helpers.parse_config_file(parsed_args.config_file)
        module_doc = configs.jouled.module_doc
        
