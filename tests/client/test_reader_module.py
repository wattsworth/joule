import os
import argparse
import asyncio
import json
import io
import numpy as np
from contextlib import redirect_stdout
from aiohttp import web
import aiohttp
from aiohttp.test_utils import unused_port
import threading
import time
import requests

from joule.client import ReaderModule
from joule.models import DataStream, Element, pipes
from tests import helpers
import warnings

warnings.simplefilter('always')


class SimpleReader(ReaderModule):
    async def run(self, parsed_args, output: pipes.Pipe):
        await output.write(parsed_args.mock_data)
        await output.close()


class InterfaceReader(ReaderModule):
    async def run(self, parsed_args, output: pipes.Pipe):
        while not self.stop_requested:
            await asyncio.sleep(0.01)

    def routes(self):
        return [web.get('/', self.index)]

    async def index(self, _):
        self.stop_requested = True
        return web.Response(text="Hello World")


class TestReaderModule(helpers.AsyncTestCase):

    def setUp(self):
        super().setUp()
        # module output is a float32_3 stream
        self.stream = DataStream(name="output", datatype=DataStream.DATATYPE.FLOAT32,
                                 elements=[Element(name="e%d" % j, index=j,
                                               display_type=Element.DISPLAYTYPE.CONTINUOUS) for j in range(3)])

    def test_writes_to_pipes(self):
        module = SimpleReader()
        (r, w) = os.pipe()

        rf = pipes.reader_factory(r)
        pipe = pipes.InputPipe(name="output", stream=self.stream, reader_factory=rf)
        pipe_arg = json.dumps(json.dumps({"outputs": {'output': {'fd': w, 'id': None, 'layout': self.stream.layout}},
                                          "inputs": {}}))
        data = helpers.create_data(self.stream.layout)
        args = argparse.Namespace(pipes=pipe_arg, socket="unset",
                                  url='http://localhost:8080',
                                  node="", api_socket="",
                                  mock_data=data)
        # run the reader module

        module.start(args)
        # check the output
        received_data = asyncio.run(pipe.read())
        np.testing.assert_array_equal(data, received_data)
        asyncio.run(pipe.close())

    def test_writes_to_stdout(self):
        module = SimpleReader()
        data = helpers.create_data(self.stream.layout, length=10)
        args = argparse.Namespace(pipes="unset",
                                  module_config="unset",
                                  url='http://localhost:8080',
                                  node="", api_socket="",
                                  socket="unset", mock_data=data)
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

    def test_reader_requires_single_output(self):
        module = SimpleReader()
        data = helpers.create_data(self.stream.layout, length=10)
        pipe_arg = json.dumps(json.dumps({"outputs": {'first': {'fd': 0, 'id': None, 'layout': self.stream.layout},
                                                      'second': {'fd': 1, 'id': None, 'layout': self.stream.layout}},
                                          "inputs": {}}))
        args = argparse.Namespace(pipes=pipe_arg,
                                  module_config="unset",
                                  socket="unset",
                                  url='http://localhost:8080',
                                  node="", api_socket="",
                                  mock_data=data)
        # run the reader module
        with self.assertLogs(level="ERROR") as logs:
            module.start(args)
        all_logs = ' '.join(logs.output).lower()
        self.assertTrue('output' in all_logs)

    def test_runs_webserver(self):
        module = InterfaceReader()
        data = helpers.create_data(self.stream.layout, length=10)
        port = unused_port()
        args = argparse.Namespace(pipes="unset", module_config="unset",
                                  socket="unset", port=port, host="127.0.0.1",
                                  url='http://localhost:8080',
                                  node="", api_socket="",
                                  mock_data=data)

        def get_page():
            time.sleep(0.5)
            resp = requests.get('http://localhost:%d' % port)
            self.assertEqual(resp.content.decode('utf8'), 'Hello World')

        getter = threading.Thread(target=get_page)
        getter.start()
        f = io.StringIO()
        with redirect_stdout(f):
            module.start(args)
        getter.join()

    def test_opens_socket(self):
        socket_path = '/tmp/interface.test'
        if os.path.exists(socket_path):
            os.unlink(socket_path)

        module = InterfaceReader()
        data = helpers.create_data(self.stream.layout, length=10)
        args = argparse.Namespace(pipes="unset", module_config="unset",
                                  url='http://localhost:8080',
                                  socket=socket_path,
                                  node="", api_socket="",
                                  mock_data=data)

        def get_page():
            time.sleep(0.5)
            resp = asyncio.run(get_page_task())
            self.assertEqual(resp, 'Hello World')
            

        async def get_page_task():
            conn = aiohttp.UnixConnector(socket_path)
            async with aiohttp.ClientSession(connector=conn,
                                             auto_decompress=False) as session:
                # proxy the request to the module
                async with session.get('http://localhost/') as resp:
                    return await resp.text()

        getter = threading.Thread(target=get_page)
        getter.start()
        f = io.StringIO()
        with redirect_stdout(f):
            module.start(args)
        getter.join()
        if os.path.exists(socket_path):
            os.unlink(socket_path)
