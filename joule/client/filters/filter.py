import argparse
import textwrap
import asyncio
import signal

from joule.client import helpers


class FilterModule:

    def __init__(self, name="Joule Filter Module"):
        self.name = name
        self.parser = ""  # initialized in build_args
        self.arg_description = ""  # optional argument description
        self.help = """TODO: how to use this module: override in child"""
        self.description = """TODO: one line description"""
    
    def custom_args(self, parser):
        # parser.add_argument("--custom_flag")
        pass

    def runtime_help(self, parsed_args):
        return self.help

    async def print_runtime_help(self, parsed_args):
        " short message explaining what filter does given the args "
        print(self.runtime_help(parsed_args))
        
    async def run(self, parsed_args, inputs, outputs):
        # some logic...
        # await output.write(np_array)
        assert False, "implement in child class"

    def stop(self):
        # override in client for alternate shutdown strategy
        print("closing...")
        self.task.cancel()
        
    def build_args(self, parser):
        helpers.add_args(parser)
        self.custom_args(parser)
        
    def start(self, parsed_args=None):
        if(parsed_args is None):
            parser = argparse.ArgumentParser(
                self.name,
                description=textwrap.dedent(self.arg_description),
                formatter_class=argparse.RawTextHelpFormatter
            )
            self.build_args(parser)
            parsed_args = parser.parse_args()
            
        self.task = self.run_as_task(parsed_args)
        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGINT, self.stop)
        loop.add_signal_handler(signal.SIGTERM, self.stop)
        try:
            loop.run_until_complete(self.task)
        except asyncio.CancelledError:
            pass
        loop.close()
        
    def run_as_task(self, parsed_args):
        (pipes_in, pipes_out) = helpers.build_pipes(parsed_args)
        if(pipes_out == {}):
            return asyncio.ensure_future(
                self.print_runtime_help(parsed_args))
        else:
            return asyncio.ensure_future(
                self.run(parsed_args, pipes_in, pipes_out))
