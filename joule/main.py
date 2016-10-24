import sys
from cliff.app import App
from cliff.commandmanager import CommandManager
import pkg_resources
import traceback

class JouleApp(App):
    def __init__(self):
        super(JouleApp, self).__init__(
            description='Joule Application',
            version = pkg_resources.require("Joule")[0].version,
            command_manager = CommandManager('joule.commands'),
            deferred_help  = True,
            )
    def initialize_app(self,argv):
        self.LOG.debug('initialize_app')

    def prepare_to_run_command(self,cmd):
        self.LOG.debug('prepare_to_run_command %s', cmd.__class__.__name__)

    def clean_up(self, cmd, result, err):
        if(err is not None):
            traceback.print_exc(file=sys.stdout)
        self.LOG.debug('got an error: %s', err)

        
def main(argv=sys.argv[1:]):
    myapp = JouleApp()
    return myapp.run(argv)

        # load config file into AppConfig
        # set up logging
        # create procs for each input file
        # enter monitoring loop


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
