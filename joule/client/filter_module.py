import asyncio
from joule.models import ConfigurationError
from . import base_module


class FilterModule(base_module.BaseModule):

    async def run(self, parsed_args, inputs, outputs):
        # some logic...
        # await output.write(np_array)
        assert False, "implement in child class"  # pragma: no cover

    def run_as_task(self, parsed_args, loop):
        # to appease type checker
        pipes_in = {}
        pipes_out = {}
        try:
            coro = self._build_pipes(parsed_args, loop)
            (pipes_in, pipes_out) = loop.run_until_complete(coro)
        except ConfigurationError as e:
            print("Configuration Error: %s" % str(e))
            exit(1)
        return asyncio.ensure_future(
            self.run(parsed_args, pipes_in, pipes_out))
