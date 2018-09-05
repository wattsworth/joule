import os
import argparse
import asyncio
import json
import numpy as np
from aiohttp import web

from joule.client import FilterModule
from joule.models import Stream, Element, pipes
from tests import helpers
import warnings

warnings.simplefilter('always')


class SimpleFilter(FilterModule):
    # multiplies data by 2
    async def run(self, parsed_args, inputs, outputs):
        try:
            while True:
                data = await inputs['to_filter'].read()
                inputs['to_filter'].consume(len(data))
                data['data'] *= 2
                await outputs['from_filter'].write(data)
        except pipes.EmptyPipe:
            pass


class TestFilterModule(helpers.AsyncTestCase):

    def setUp(self):
        super().setUp()
        # module output is a float32_3 stream
        self.output = Stream(name="output", datatype=Stream.DATATYPE.FLOAT32,
                             elements=[Element(name="e%d" % j, index=j,
                                               display_type=Element.DISPLAYTYPE.CONTINUOUS) for j in range(3)])
        # module input is a float32_3 stream
        self.input = Stream(name="input", datatype=Stream.DATATYPE.FLOAT32,
                            elements=[Element(name="e%d" % j, index=j,
                                              display_type=Element.DISPLAYTYPE.CONTINUOUS) for j in range(3)])

    def test_writes_to_pipes(self):
        module = SimpleFilter()
        (r, w_module) = os.pipe()
        loop = asyncio.get_event_loop()
        rf = pipes.reader_factory(r, loop)
        from_filter = pipes.InputPipe(name="from_filter", stream=self.output, reader_factory=rf)
        (r_module, w) = os.pipe()
        loop = asyncio.get_event_loop()
        wf = pipes.writer_factory(w, loop)
        to_filter = pipes.OutputPipe(name="to_filter", stream=self.input, writer_factory=wf)

        pipe_arg = json.dumps(json.dumps({"outputs": {'from_filter': {'fd': w_module, 'stream': self.output.to_json()}},
                                          "inputs": {'to_filter': {'fd': r_module, 'stream': self.input.to_json()}}}))
        data = helpers.create_data(self.input.layout)
        self.loop.run_until_complete(to_filter.write(data))
        self.loop.run_until_complete(to_filter.close())
        args = argparse.Namespace(pipes=pipe_arg, socket="unset")
        # run the reader module
        loop = asyncio.new_event_loop()
        loop.set_debug(True)
        asyncio.set_event_loop(loop)
        module.start(args)
        asyncio.set_event_loop(self.loop)
        # check the output
        received_data = self.loop.run_until_complete(from_filter.read())
        np.testing.assert_array_equal(data['timestamp'], received_data['timestamp'])
        np.testing.assert_array_almost_equal(data['data']*2, received_data['data'])

    def test_error_on_invalid_params(self):
        # if pipes is not set, must specify a module_config
        module = SimpleFilter()
        args = argparse.Namespace(socket='none', pipes='unset',
                                  module_config='unset',
                                  start_time=None, end_time=None)
        # run the module
        loop = asyncio.new_event_loop()
        loop.set_debug(True)
        asyncio.set_event_loop(loop)
        with self.assertLogs(level="ERROR") as logs:
            module.start(args)
        log_dump = ' '.join(logs.output).lower()
        self.assertTrue('module_config' in log_dump)
        asyncio.set_event_loop(self.loop)
