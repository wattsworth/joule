
from joule.procdb import client as procdb_client
from cliff.lister import Lister
import psutil
from joule.daemon import module
from . import helpers


class ModulesCmd(Lister):
    "Print the status of the joule daemon"

    def __init__(self, app, app_args, cmd_name=None):
        super(ModulesCmd, self).__init__(app, app_args, cmd_name)

    def get_parser(self, prog_name):
        parser = super(ModulesCmd, self).get_parser(prog_name)
        parser.add_argument('--config-file', dest="config_file")
        return parser

    def take_action(self, parsed_args):

        configs = helpers.parse_config_file(parsed_args.config_file)
        headers = ('Module', 'Sources', 'Destinations', 'Status', 'CPU', 'mem')
        format_type = parsed_args.formatter  # print differently if json output

        procdb = procdb_client.SQLClient(configs.procdb.db_path,
                                         configs.procdb.max_log_lines)
        modules = procdb.find_all_modules()
        module_stats = []
        for m in modules:
            (status, cpu, mem) = self._get_info(m, format_type)
            name = self._get_name(m, format_type)
            dests = self._list_paths(m.destination_paths.values(), format_type)
            sources = self._list_paths(m.source_paths.values(), format_type)
            module_stats.append([name, sources, dests, status, cpu, mem])

        return (headers, module_stats)

    def _get_name(self, my_module, formatter):
        if(formatter == "json"):
            return {"name": my_module.name, "description": my_module.description}
        else:
            if(my_module.description != ""):
                return "{name}:\n{description}".format(name=my_module.name,
                                                       description=my_module.description)
            else:
                return my_module.name

    def _get_info(self, my_module, formatter):
        cpu = "--"
        mem = "--"
        try:
            process = psutil.Process(my_module.pid)
            # retrieve and format memory usage
            pct = process.memory_percent()
            pmem = process.memory_info().rss
            if(formatter == 'json'):
                mem = [pmem, pct]
            else:
                mem = "%d MB (%d%%)" % (pmem // (1024 * 1024), pct * 100)
            # retrieve and format CPU usage
            c = process.cpu_percent(interval=1.0)
            if(formatter == 'json'):
                cpu = c
            else:
                cpu = "%d%%" % (c)
            # set the status
            status = my_module.status
        except Exception as e:
            status = module.STATUS_FAILED
        return (status, cpu, mem)

    def _list_paths(self, paths, formatter):
        if(formatter == "json"):
            return list(paths)
        else:
            return "\n".join(paths)
