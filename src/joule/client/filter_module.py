import asyncio
import logging

import joule.utilities
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

    async def run_as_task(self, parsed_args, app) -> asyncio.Task:
        (input_streams, output_streams) = await self._parse_streams(parsed_args)
        missing_intervals = await self._compute_missing_intervals(input_streams, output_streams, parsed_args)
        return asyncio.create_task(self._task(missing_intervals, input_streams, output_streams, parsed_args, app))

    async def _task(self, pending_intervals, input_streams, output_streams, parsed_args, app):
        if len(pending_intervals) == 0:
            if len(input_streams) == 0:
                print("No inputs, cannot run on historic data, specify --live to produce outputs")
            else:
                print("Nothing to do, data is already filtered")
            return asyncio.create_task(asyncio.sleep(0))
        # if an interval is None this indicates the pipes should be live
        for interval in pending_intervals:
            if interval is not None:
                print("%s => %s" % (joule.utilities.timestamp_to_human(interval[0]),
                                    joule.utilities.timestamp_to_human(interval[1])))
            elif parsed_args.live:
                print("Running filter on live input data")
            try:
                (pipes_in, pipes_out) = await self._build_pipes_new(interval, input_streams,
                                                                    output_streams, parsed_args.pipes)
            except errors.ApiError as e:
                logging.error(str(e))
                return asyncio.create_task(asyncio.sleep(0))
            await self.setup(parsed_args, app, pipes_in, pipes_out)
            try:
                await self.run(parsed_args, pipes_in, pipes_out)
            except (asyncio.CancelledError, errors.EmptyPipeError):
                pass
            for pipe in pipes_out.values():
                await pipe.close()
