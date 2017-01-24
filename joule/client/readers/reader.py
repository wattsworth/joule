import argparse
from joule.client import helpers
import asyncio
import signal


class ReaderModule:

    def __init__(self, name="Joule Reader Module"):
        self.name = name
        self.parser = ""  # initialized in build_args
        self.help = """TODO: how to use this module: override in child"""
        self.description = """TODO: one line description"""
    
    def custom_args(self, parser):
        # parser.add_argument("--custom_flag")
        pass

    async def run(self, parsed_args, output):
        # some logic...
        # await output.write(np_array)
        assert False, "implement in child class"

    def stop(self):
        # override in client for alternate shutdown strategy
        # TODO: this doesn't seem to work, maybe a problem with Cliff?
        print("closing...")
        self.task.cancel()
        
    def build_args(self, parser):
        helpers.add_args(parser)
        self.custom_args(parser)
        
    def start(self, argv=None):
        parser = argparse.ArgumentParser(self.name)
        self.build_args(parser)
        parsed_args = parser.parse_args()
        self.task = self.run_as_task(parsed_args)
        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGINT, self.stop)
        loop.add_signal_handler(signal.SIGTERM, self.stop)
        loop.run_until_complete(self.task)
        loop.close()
        
    def run_as_task(self, parsed_args):
        (pipes_in, pipes_out) = helpers.build_pipes(parsed_args)
        if(pipes_out == {}):
            output = StdoutPipe()
        else:
            output = pipes_out['output']
        return asyncio.ensure_future(self.run(parsed_args, output))

    
class StdoutPipe:

    async def write(self, data):
        for row in data:
            ts = row[0]
            vals = row[1:]
            print("%d %s" % (ts, " ".join([repr(x) for x in vals])))
