import asyncio

from . import base_module


class CompositeModule(base_module.BaseModule):

    async def setup(self, parsed_args, inputs, outputs):
        # call run for other modules
        # return [coro, coro, ...]
        assert False, "implement in child class"

    def run_as_task(self, parsed_args, loop):
        coro = self.build_pipes(parsed_args)
        (pipes_in, pipes_out) = loop.run_until_complete(coro)
        coro = self.setup(parsed_args,
                          pipes_in,
                          pipes_out)
        tasks = loop.run_until_complete(coro)
        return asyncio.gather(*tasks)