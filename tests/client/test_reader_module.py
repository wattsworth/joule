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
import unittest

from joule.client import ReaderModule
from joule.models import Stream, Element, pipes
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
        self.stream = Stream(name="output", datatype=Stream.DATATYPE.FLOAT32,
                             elements=[Element(name="e%d" % j, index=j,
                                               display_type=Element.DISPLAYTYPE.CONTINUOUS) for j in range(3)])

    def test_writes_to_pipes(self):
        module = SimpleReader()
        (r, w) = os.pipe()
        loop = asyncio.get_event_loop()
        rf = pipes.reader_factory(r, loop)
        pipe = pipes.InputPipe(name="output", stream=self.stream, reader_factory=rf)
        pipe_arg = json.dumps(json.dumps({"outputs": {'output': {'fd': w, 'stream': self.stream.to_json()}},
                                          "inputs": {}}))
        data = helpers.create_data(self.stream.layout)
        args = argparse.Namespace(pipes=pipe_arg, socket="unset",
                                  url='http://localhost:8080',
                                  mock_data=data)
        # run the reader module
        loop = asyncio.new_event_loop()
        loop.set_debug(True)
        asyncio.set_event_loop(loop)
        module.start(args)
        asyncio.set_event_loop(self.loop)
        # check the output
        received_data = self.loop.run_until_complete(pipe.read())
        np.testing.assert_array_equal(data, received_data)
        self.loop.run_until_complete(pipe.close())
        self.loop.close()

    def test_writes_to_stdout(self):
        module = SimpleReader()
        data = helpers.create_data(self.stream.layout, length=10)
        args = argparse.Namespace(pipes="unset",
                                  module_config="unset",
                                  url='http://localhost:8080',
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

    def test_reader_requires_output(self):
        module = SimpleReader()
        data = helpers.create_data(self.stream.layout, length=10)
        pipe_arg = json.dumps(json.dumps({"outputs": {'badname': {'fd': 0, 'stream': self.stream.to_json()}},
                                          "inputs": {}}))
        args = argparse.Namespace(pipes=pipe_arg,
                                  module_config="unset",
                                  socket="unset",
                                  url='http://localhost:8080',
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
        module = InterfaceReader()
        data = helpers.create_data(self.stream.layout, length=10)
        args = argparse.Namespace(pipes="unset", module_config="unset",
                                  url='http://localhost:8080',
                                  socket="joule.test",
                                  mock_data=data)

        def get_page():
            time.sleep(0.5)
            loop = asyncio.new_event_loop()
            resp = loop.run_until_complete(get_page_task())
            self.assertEqual(resp, 'Hello World')
            loop.close()

        async def get_page_task():
            conn = aiohttp.UnixConnector(path=b'\x00'+'joule.test'.encode('ascii'))
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
