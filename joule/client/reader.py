import argparse
import joule.utils.client
import asyncio


class ReaderModule:

    def __init__(self, name="Joule Reader Module"):
        self.name = name
        self.parser = ""  # initialized in build_args

    def help(self):
        return """TODO: how to use this module: override in child"""

    def description(self):
        return """TODO: one line description"""
    
    def custom_args(self, parser):
        # parser.add_argument("--custom_flag")
        pass

    async def process(self, parsed_args, output):
        # some logic...
        # await output.write(np_array)
        assert False, "implement in child class"

    def build_args(self, parser):
        joule.utils.client.add_args(parser)
        self.custom_args(parser)
        
    def run(self, parsed_args):
        (pipes_in, pipes_out) = joule.utils.client.build_pipes(parsed_args)
        if(pipes_out == {}):
            output = StdoutPipe()
        else:
            output = pipes_out['output']
            
        task = asyncio.ensure_future(self.process(parsed_args, output))
        loop = asyncio.get_event_loop()
        loop.run_until_complete(task)
        loop.close()

    def start(self, argv=None):
        parser = argparse.ArgumentParser(self.name)
        self.build_args(parser)
        parsed_args = parser.parse_args()
        self.run(parsed_args)
        
        
class StdoutPipe:

    async def write(data):
        for row in data:
            print(row)
