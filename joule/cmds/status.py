
import logging
from joule.procdb import client as procdb_client
from cliff.lister import Lister

class StatusCmd(Lister):
    "Print the status of the joule daemon"

    log = logging.getLogger(__name__)
    def __init__(self, app, app_args, cmd_name=None):
        super(StatusCmd, self).__init__(app,app_args,cmd_name)
           
    
    def take_action(self, parsed_args):
        modules = procdb_client.input_modules()
        return (('Module Name','Destination Path','Status'),
                ((m.name,m.destination.path,m.status,m.config_file) for m in modules))
