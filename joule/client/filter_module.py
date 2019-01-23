import asyncio
import logging

from . import base_module
from joule import errors


class FilterModule(base_module.BaseModule):

    async def setup(self, parsed_args, app, inputs, outputs):
        """
        Configure the module, executes before :meth:`run`

        Args:
            parsed_args:
            app:
            inputs:
            outputs:

        Returns:

        """
        pass

    async def run(self, parsed_args, inputs, outputs):
        """
        This method must be implemented. It should run in a loop, if it returns the module stops.

        Args:
            parsed_args: parsed command line arguments, configure with :meth:`joule.BaseModule.custom_args`
            inputs: pipe connections to input streams indexed by name (specified in the module configuration file).
            outputs: pipe connections to output streams indexed by name (specified in the module configuration file).

        .. code-block:: python

            class ModuleDemo(FilterModule):

                def run(self, parsed_args, inputs, outputs):
                    raw = inputs["raw"]
                    filtered = outputs["filtered"]
                    # this filter just passes the input through to the output
                     while(not self.stop_requested):
                        data = await raw.read()
                        await filtered.write(data)
                        raw.consume(len(data))

                #... other module code
        """
        assert False, "implement in child class"  # pragma: no cover

    def run_as_task(self, parsed_args, app, loop):
        try:
            coro = self._build_pipes(parsed_args)
            (pipes_in, pipes_out) = loop.run_until_complete(coro)
        except errors.ApiError as e:
            logging.error(str(e))
            return loop.create_task(asyncio.sleep(0))
        loop.run_until_complete(self.setup(parsed_args, app, pipes_in, pipes_out))
        return asyncio.ensure_future(
            self.run(parsed_args, pipes_in, pipes_out))
