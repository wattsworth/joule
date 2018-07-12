import asyncio

from . import base_module


class FilterModule(base_module.BaseModule):
        
    async def run(self, parsed_args, inputs, outputs):
        # some logic...
        # await output.write(np_array)
        assert False, "implement in child class"

    def run_as_task(self, parsed_args, loop):
        coro = self._build_pipes(parsed_args, loop)
        (pipes_in, pipes_out) = loop.run_until_complete(coro)
        return asyncio.ensure_future(
            self.run(parsed_args, pipes_in, pipes_out))
