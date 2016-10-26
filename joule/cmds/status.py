
import logging
from joule.procdb import client as procdb_client
from cliff.lister import Lister
import psutil

class StatusCmd(Lister):
    "Print the status of the joule daemon"

    log = logging.getLogger(__name__)
    def __init__(self, app, app_args, cmd_name=None):
        super(StatusCmd, self).__init__(app,app_args,cmd_name)
        self.cpu_count = psutil.cpu_count()

    def print_mem(self,process):
        m = process.memory_percent()
        pmem = process.memory_info()
        return "%d MB (%d%%)"%(pmem.rss//(1024*1024), m*100)

    def print_cpu(self,process):
        c =  process.cpu_percent(interval=1.0)
        return "%d%%"%(c)
    
    def take_action(self, parsed_args):
        modules = procdb_client.input_modules()
        res = []
        for m in modules:
            cpu = "--"; mem = "--";
            try:
                process = psutil.Process(m.pid)
                cpu = self.print_cpu(process)
                mem = self.print_mem(process)
            except Exception as e:
                m.status = "failed"
            res.append([m.name,m.destination.path,m.status,cpu,mem])
        return (('Module Name','Destination Path','Status','CPU','mem'),res)
