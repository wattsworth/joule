import multiprocessing
import os
import argparse
import asyncio
import json
import io
import numpy as np
import tempfile
from contextlib import redirect_stdout

from joule.client import ReaderModule
from joule.models import Stream, Element, pipes
from tests import helpers
import warnings


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
        module_proc = multiprocessing.Process(target=module.start, args=(args,))
        # run the reader module
        module_proc.start()
        os.close(w)  # close our copy of the write side
        module_proc.join()  # wait for reader to finish
        # check the output
        received_data = loop.run_until_complete(pipe.read())
        np.testing.assert_array_equal(data, received_data)

    def test_writes_to_stdout(self):
        module = Reader()
        data = helpers.create_data(self.stream.layout, length=10)
        args = argparse.Namespace(pipes="unset", module_config="unset", socket="unset", mock_data=data)
        module_proc = multiprocessing.Process(target=module.start, args=(args,))
        # capture stdout to a file
        with tempfile.TemporaryFile(mode='w+') as output_file:
            # run the reader module
            with redirect_stdout(output_file):
                module_proc.start()
                module_proc.join()  # wait for reader to finish
            # check the output
            output_file.seek(0,0)
            for row in data:
                output = output_file.readline().split(' ')
                ts = int(output[0])
                data = [float(x) for x in output[1:]]
                self.assertEqual(ts, row['timestamp'])
                np.testing.assert_array_almost_equal(data, row['data'])

    def test_runs_webserver(self):
        pass

    def test_opens_socket(self):
        pass
