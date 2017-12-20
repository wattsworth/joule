import asyncio

from joule.client import JouleModule


class CompositeModule(JouleModule):

    async def setup(self, parsed_args, inputs, outputs):
        # call run for other modules
        # return [coro, coro, ...]
        assert False, "implement in child class"

    def run_as_task(self, parsed_args, loop):
        coro = self.build_pipes(parsed_args)
        (pipes_in, pipes_out) = loop.run_until_complete(coro)

        return asyncio.gather(*self.setup(parsed_args,
                                          pipes_in,
                                          pipes_out))
