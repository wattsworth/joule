import os
import argparse
import asyncio
import json
import unittest
import numpy as np

from unittest import mock
from joule.api import BaseNode

from joule.client import FilterModule
from joule.models import DataStream, Element, pipes
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
        self.output = DataStream(name="output", datatype=DataStream.DATATYPE.FLOAT32,
                                 elements=[Element(name="e%d" % j, index=j,
                                               display_type=Element.DISPLAYTYPE.CONTINUOUS) for j in range(3)])
        # module input is a float32_3 stream
        self.input = DataStream(name="input", datatype=DataStream.DATATYPE.FLOAT32,
                                elements=[Element(name="e%d" % j, index=j,
                                              display_type=Element.DISPLAYTYPE.CONTINUOUS) for j in range(3)])

    def test_writes_to_pipes(self):
        module = SimpleFilter()
        (r, w_module) = os.pipe()

        rf = pipes.reader_factory(r)
        from_filter = pipes.InputPipe(name="from_filter", stream=self.output, reader_factory=rf)
        (r_module, w) = os.pipe()

        wf = pipes.writer_factory(w)
        to_filter = pipes.OutputPipe(name="to_filter", stream=self.input, writer_factory=wf)

        pipe_arg = json.dumps(
            json.dumps({"outputs": {'from_filter': {'fd': w_module, 'id': 2, 'layout': self.output.layout}},
                        "inputs": {'to_filter': {'fd': r_module, 'id': 3, 'layout': self.input.layout}}}))
        data = helpers.create_data(self.input.layout)
        async def runner():
            await to_filter.write(data)
            await to_filter.close()
        asyncio.run(runner())
        args = argparse.Namespace(pipes=pipe_arg, socket="unset",
                                  node="", api_socket="", live=False,
                                  url='http://localhost:8080')
        # run the reader module

        class MockNode(BaseNode):
            def __init__(self):
                self.session = mock.Mock()
                self.session.close = unittest.mock.AsyncMock()
                pass

        with mock.patch('joule.client.base_module.node') as mock_node_pkg:
            node = MockNode()
            node.data_stream_get = unittest.mock.AsyncMock(return_value=self.output)
            mock_node_pkg.UnixNode = mock.Mock(return_value=node)
            module.start(args)
            # make sure the API was used to retrieve stream objects
            self.assertEqual(node.data_stream_get.await_count, 2)

        # check the output
        received_data = asyncio.run(from_filter.read())
        np.testing.assert_array_equal(data['timestamp'], received_data['timestamp'])
        np.testing.assert_array_almost_equal(data['data'] * 2, received_data['data'])
        asyncio.run(from_filter.close())

    def test_error_on_invalid_params(self):
        # if pipes is not set, must specify a module_config
        module = SimpleFilter()
        args = argparse.Namespace(socket='none', pipes='unset',
                                  url='http://localhost:8080',
                                  module_config='unset',
                                  node="", api_socket="",
                                  start_time=None, end_time=None)
        # run the module
        with self.assertLogs(level="ERROR") as logs:
            module.start(args)
        log_dump = ' '.join(logs.output).lower()
        self.assertTrue('module_config' in log_dump)
