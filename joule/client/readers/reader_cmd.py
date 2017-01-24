from cliff.command import Command
from .random import RandomReader
from .file import FileReader

import asyncio


class ReaderCmd(Command):
    "Built-in Reader Modules"
    
    def __init__(self, app, app_args, cmd_name=None):
        super(ReaderCmd, self).__init__(app, app_args, cmd_name)
        self.module_parsers = {}  # generated in get_parser
        self.modules = {
            "random": RandomReader(),
            "file": FileReader()
        }

    def get_parser(self, prog_name):
        parser = super(ReaderCmd, self).get_parser(prog_name)
        subparsers = parser.add_subparsers()
        for (name, reader) in self.modules.items():
            my_parser = subparsers.add_parser(name,
                                              help=reader.description)
            reader.build_args(my_parser)
            my_parser.set_defaults(reader=name)
            self.module_parsers[name] = my_parser
        # now add a help option
        help = subparsers.add_parser("help", help="help for a reader module")
        help.add_argument("module", choices=self.modules.keys())
        help.set_defaults(reader="help")
        self.parser = parser
        return parser

    def take_action(self, parsed_args):
        if(not("reader" in parsed_args)):
            self.parser.print_help()
            return

        if(parsed_args.reader == "help"):
            module_name = parsed_args.module
            print(self.modules[module_name].help)

            self.module_parsers[module_name].print_help()
            return
        reader = self.modules[parsed_args.reader]
        task = reader.run_as_task(parsed_args)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(task)
        loop.close()



