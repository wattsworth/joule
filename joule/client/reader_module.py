import asyncio
import numpy as np
import logging
from . import base_module


class ReaderModule(base_module.BaseModule):

    async def run(self, parsed_args, output):
        # some logic...
        # await output.write(np_array)
        assert False, "implement in child class"  # pragma: no cover

    def run_as_task(self, parsed_args, loop):
        # check if we should use stdout (no fd's and no configs)
        if(parsed_args.pipes == "unset" and
           parsed_args.module_config == "unset"):
            output = StdoutPipe()
        else:
            coro = self._build_pipes(parsed_args, loop)
            (pipes_in, pipes_out) = loop.run_until_complete(coro)
            if 'output' not in pipes_out:
                logging.error("Reader Module must a have a single output called 'output'")
                return loop.create_task(asyncio.sleep(0))
            output = pipes_out['output']
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
