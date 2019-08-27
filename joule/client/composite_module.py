import asyncio
import argparse
import logging
from typing import Dict

from joule.models.pipes.pipe import Pipe as Pipe
from joule import errors
from . import base_module


class CompositeModule(base_module.BaseModule):

    async def setup(self, parsed_args: argparse.Namespace, inputs: Dict[str, Pipe],
                    outputs: Dict[str, Pipe], loop: asyncio.AbstractEventLoop):
        """
        This method must be implemented

        Args:
            parsed_args: parsed command line arguments
            inputs: pipe connections to input streams. Keys are the names specified in the module configuration file
            outputs: pipe connections ot output streams. Keys are the names specified in the module configuration
            loop: the current event loop

        Returns:
            array of coroutine objects

        """

        assert False, "implement in child class"  # pragma: no cover

    async def run_as_task(self, parsed_args, app, loop) -> asyncio.Task:
        try:
            (pipes_in, pipes_out) = await self._build_pipes(parsed_args)
        except errors.ApiError as e:
            logging.error(str(e))
            return loop.create_task(asyncio.sleep(0))
        tasks = await self.setup(parsed_args,
                                 pipes_in,
                                 pipes_out,
                                 loop)
        return asyncio.gather(*tasks)
