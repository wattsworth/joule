import os
import argparse
import asyncio
import json
import io
import numpy as np
import unittest
from contextlib import redirect_stdout

from joule.client import ReaderModule
from joule.models import Stream, Element, pipes
from tests import helpers
import warnings

warnings.simplefilter('always')

class Reader(ReaderModule):
    async def run(self, parsed_args, output: pipes.Pipe):
        await output.write(parsed_args.mock_data)


class TestBaseModule(helpers.AsyncTestCase):

    def setUp(self):
        super().setUp()
        # module output is a float32_3 stream
        self.stream = Stream(name="output", datatype=Stream.DATATYPE.FLOAT32,
                             elements=[Element(name="e%d" % j, index=j,
                                               display_type=Element.DISPLAYTYPE.CONTINUOUS) for j in range(3)])
    #@unittest.skip("msg")
    def test_writes_to_pipes(self):
        module = Reader()
        (r, w) = os.pipe()
        loop = asyncio.get_event_loop()
        rf = pipes.reader_factory(r, loop)
        pipe = pipes.InputPipe(name="output", stream=self.stream, reader_factory=rf)
        pipe_arg = json.dumps(json.dumps({"outputs": {'output': {'fd': w, 'stream': self.stream.to_json()}},
                                          "inputs": {}}))
        data = helpers.create_data(self.stream.layout)
        args = argparse.Namespace(pipes=pipe_arg, socket="unset", mock_data=data)
        # run the reader module
        loop = asyncio.new_event_loop()
        loop.set_debug(True)
        asyncio.set_event_loop(loop)
        module.start(args)
        asyncio.set_event_loop(self.loop)
        # check the output
        received_data = self.loop.run_until_complete(pipe.read())
        np.testing.assert_array_equal(data, received_data)

    def test_writes_to_stdout(self):
        module = Reader()
        data = helpers.create_data(self.stream.layout, length=10)
        args = argparse.Namespace(pipes="unset", module_config="unset", socket="unset", mock_data=data)
        # run the reader module
        f = io.StringIO()
        with redirect_stdout(f):
            module.start(args)
        lines = f.getvalue().split('\n')
        for i in range(len(data)):
            output = lines[i].split(' ')
            ts = int(output[0])
            rx_data = [float(x) for x in output[1:]]
            self.assertEqual(ts, data['timestamp'][i])
            np.testing.assert_array_almost_equal(rx_data, data['data'][i])

    def test_runs_webserver(self):
        pass

    def test_opens_socket(self):
        pass
