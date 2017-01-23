import argparse
import joule.utils.client
import asyncio
import signal


class FilterModule:

    def __init__(self, name="Joule Filter Module"):
        self.name = name
        self.parser = ""  # initialized in build_args

    def help(self):
        return """TODO: how to use this module: override in child"""

    def description(self):
        return """TODO: one line description"""
    
    def custom_args(self, parser):
        # parser.add_argument("--custom_flag")
        pass

    def runtime_help(self, parsed_args):
        return "TODO: implement in child"

    async def print_runtime_help(self, parsed_args):
        " short message explaining what filter does given the args "
        print(self.runtime_help(parsed_args))
        
    async def run(self, parsed_args, inputs, outputs):
        # some logic...
        # await output.write(np_array)
        assert False, "implement in child class"

    def stop(self):
        # override in client for alternate shutdown strategy
        # TODO: this doesn't seem to work, maybe a problem with Cliff?
        print("closing...")
        self.task.cancel()
        
    def build_args(self, parser):
        joule.utils.client.add_args(parser)
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
        (pipes_in, pipes_out) = joule.utils.client.build_pipes(parsed_args)
        if(pipes_out == {}):
            return asyncio.ensure_future(
                self.print_runtime_help(parsed_args))
        else:
            return asyncio.ensure_future(
                self.run(parsed_args, pipes_in, pipes_out))
