import asyncio
#from joule.models import ConfigurationError
from . import base_module


class FilterModule(base_module.BaseModule):


    async def setup(self, parsed_args, app, inputs, outputs):
        pass

    async def run(self, parsed_args, inputs, outputs):
        # some logic...
        # await output.write(np_array)
        assert False, "implement in child class"  # pragma: no cover

    def run_as_task(self, parsed_args, app, loop):
        coro = self._build_pipes(parsed_args, loop)
        (pipes_in, pipes_out) = loop.run_until_complete(coro)

        loop.run_until_complete(self.setup(parsed_args, app, pipes_in, pipes_out))
        return asyncio.ensure_future(
            self.run(parsed_args, pipes_in, pipes_out))
