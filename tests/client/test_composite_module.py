import os
import argparse
import asyncio
import json
import numpy as np
from unittest import mock
import asynctest

from .test_filter_module import SimpleFilter
from .test_reader_module import SimpleReader
from joule.client import CompositeModule
from joule.api import BaseNode, DataStream
from joule.models import DataStream, Element, pipes
from joule import api
from tests import helpers
import warnings

warnings.simplefilter('always')


class SimpleComposite(CompositeModule):
    # runs the simple reader and simple filter
    # as a composite module
    async def setup(self, parsed_args, inputs, outputs):
        reader_module = SimpleReader()
        filter_module = SimpleFilter()

        pipe = pipes.LocalPipe("float32_3")
        reader_task = reader_module.run(parsed_args, pipe)
        filter_task = filter_module.run(parsed_args, {'to_filter': pipe},
                                        {'from_filter': outputs['output']})
        return [reader_task, filter_task]


class TestCompositeModule(helpers.AsyncTestCase):

    def setUp(self):
        super().setUp()
        # module output is a float32_3 stream
        self.stream = DataStream(name="output", datatype=DataStream.DATATYPE.FLOAT32,
                                 elements=[Element(name="e%d" % j, index=j,
                                               display_type=Element.DISPLAYTYPE.CONTINUOUS) for j in range(3)])

    def test_runs_composited_modules(self):
        module = SimpleComposite()
        (r, w) = os.pipe()
        module_loop = asyncio.new_event_loop()
        rf = pipes.reader_factory(r)
        pipe = pipes.InputPipe(name="output", stream=self.stream, reader_factory=rf)
        pipe_arg = json.dumps(json.dumps({"outputs": {'output': {'fd': w, 'id': None, 'layout': self.stream.layout}},
                                          "inputs": {}}))
        data = helpers.create_data(self.stream.layout)
        args = argparse.Namespace(pipes=pipe_arg, socket="unset",
                                  node="", api_socket="",
                                  url='http://localhost:8080',
                                  mock_data=data)
        # run the composite module
        asyncio.set_event_loop(module_loop)
        module.start(args)
        asyncio.set_event_loop(self.loop)
        # check the output
        received_data = self.loop.run_until_complete(pipe.read())
        np.testing.assert_array_equal(data['timestamp'], received_data['timestamp'])
        np.testing.assert_array_almost_equal(data['data'] * 2, received_data['data'])
        self.loop.run_until_complete(pipe.close())
        self.loop.close()

    def test_handles_bad_pipe_configs(self):
        args = argparse.Namespace(pipes="invalid config", socket="unset",
                                  node="", api_socket="",
                                  url='http://localhost:8080')
        loop = asyncio.new_event_loop()
        loop.set_debug(True)
        asyncio.set_event_loop(loop)
        module = SimpleComposite()
        with self.assertLogs(level="ERROR"):
            module.start(args)
        asyncio.set_event_loop(self.loop)
        if not loop.is_closed():
            loop.close()
