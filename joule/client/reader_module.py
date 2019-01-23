import asyncio
import numpy as np
import logging
import argparse
import sys

from joule.client.base_module import BaseModule
from joule.models.pipes import Pipe
from joule import errors


class ReaderModule(BaseModule):
    """
    Inherit from this class and implement a :meth:`run` coroutine to create a Joule reader module.
    Other methods documented below may be implemented as desired.
    """

    async def setup(self, parsed_args, app, output):
        """
        Configure the module, executes before :meth:`run`

        Args:
            parsed_args:
            app:
            output:

        """
        pass

    async def run(self, parsed_args: argparse.Namespace, output: Pipe):
        """
        This method must be implemented. It should run in a loop, if it returns the module
        stops.

        Args:
            parsed_args: command line arguments, configure with :meth:`custom_args`
            output: pipe connection to the output data stream

        .. code-block:: python

            class ModuleDemo(ReaderModule):

                def run(self, parsed_args, output):
                     while(not self.stop_requested):
                        data = self.read_sensor()
                        await output.write(data)

                def self.read_sensor(self) -> np.ndarray:
                    # custom logic specific to the reader

                #... other module code

        """
        assert False, "implement in child class"  # pragma: no cover

    def run_as_task(self, parsed_args, app, loop):
        # check if we should use stdout (no fd's and no configs)
        if (parsed_args.pipes == "unset" and
                parsed_args.module_config == "unset"):
            output = StdoutPipe()
        else:
            try:
                coro = self._build_pipes(parsed_args)
                (pipes_in, pipes_out) = loop.run_until_complete(coro)
            except errors.ApiError as e:
                logging.error(str(e))
                return loop.create_task(asyncio.sleep(0))
            if 'output' not in pipes_out:
                logging.error("Reader Module must a have a single output called 'output'")
                return loop.create_task(asyncio.sleep(0))
            output = pipes_out['output']
        loop.run_until_complete(self.setup(parsed_args, app, output))
        return loop.create_task(self.run(parsed_args, output))


class StdoutPipe:
    @staticmethod
    async def write(data: np.ndarray):
        # check if this is a structured array, if so flatten it
        if data.ndim == 1:
            data = np.c_[data['timestamp'][:, None], data['data']]
        for row in data:
            ts = row[0]
            vals = row[1:]
            print("%d %s" % (ts, " ".join([repr(x) for x in vals])))

    async def close_interval(self):
        print("--- interval gap ---", file=sys.stderr)

    async def close(self):
        pass
