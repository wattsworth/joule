import asyncio

from joule.client import JouleModule


class ReaderModule(JouleModule):

    async def run(self, parsed_args, output):
        # some logic...
        # await output.write(np_array)
        assert False, "implement in child class"
        
    def run_as_task(self, parsed_args, loop):
        coro = self.build_pipes(parsed_args)
        (pipes_in, pipes_out) = loop.run_until_complete(coro)
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
