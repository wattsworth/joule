import asyncio

from . import base_module


class ReaderModule(base_module.BaseModule):

    async def run(self, parsed_args, output):
        # some logic...
        # await output.write(np_array)
        assert False, "implement in child class"

    def run_as_task(self, parsed_args, loop):
        # check if we should use stdout (no fd's and no configs)
        print("here")
        if(parsed_args.pipes=="unset" and parsed_args.module_config=="unset"):
            output = StdoutPipe()
        else:
            coro = self.build_pipes(parsed_args)
            (pipes_in, pipes_out) = loop.run_until_complete(coro)
            output = pipes_out['output']
        return asyncio.ensure_future(self.run(parsed_args, output))
    
class StdoutPipe:

    async def write(self, data):
        for row in data:
            ts = row[0]
            vals = row[1:]
            print("%d %s" % (ts, " ".join([repr(x) for x in vals])))
