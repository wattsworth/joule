from cliff.command import Command
from .mean import MeanFilter
from .median import MedianFilter
from .merge import MergeFilter
import asyncio


class FilterCmd(Command):
    "Built-in Filter Modules"
    
    def __init__(self, app, app_args, cmd_name=None):
        super(FilterCmd, self).__init__(app, app_args, cmd_name)
        self.module_parsers = {}  # generated in get_parser
        self.modules = {
            "mean": MeanFilter(),
            "median": MedianFilter(),
            "merge": MergeFilter()
        }

    def get_parser(self, prog_name):
        parser = super(FilterCmd, self).get_parser(prog_name)
        subparsers = parser.add_subparsers()
        for (name, filter) in self.modules.items():
            my_parser = subparsers.add_parser(name,
                                              help=filter.description)
            filter.build_args(my_parser)
            my_parser.set_defaults(filter=name)
            self.module_parsers[name] = my_parser
        # now add a help option
        help = subparsers.add_parser("help", help="help for a filter module")
        help.add_argument("module", choices=self.modules.keys())
        help.set_defaults(filter="help")
        self.parser = parser
        return parser

    def take_action(self, parsed_args):
        if(not("filter" in parsed_args)):
            self.parser.print_help()
            return

        if(parsed_args.filter == "help"):
            module_name = parsed_args.module
            print(self.modules[module_name].help)

            self.module_parsers[module_name].print_help()
            return
        filter = self.modules[parsed_args.filter]
        task = filter.run_as_task(parsed_args)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(task)
        loop.close()



