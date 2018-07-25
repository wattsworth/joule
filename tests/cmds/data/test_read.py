import unittest
from click.testing import CliRunner
import os
import signal
import multiprocessing
from aiohttp.test_utils import unused_port
import warnings
import time
import numpy as np

from ..fake_joule import FakeJoule, FakeJouleTestCase
from joule.cli import main
from joule.models import Stream, Element, StreamInfo
from tests import helpers

warnings.simplefilter('always')


class TestDataRead(FakeJouleTestCase):

    def test_reads_data(self):
        server = FakeJoule()
        # create the source stream
        src = Stream(id=0, name="source", keep_us=100, datatype=Stream.DATATYPE.FLOAT32)
        src.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in range(3)]
        # source has 100 rows of data between [0, 100]
        src_data = helpers.create_data(src.layout)
        src_info = StreamInfo(int(src_data['timestamp'][0]), int(src_data['timestamp'][-1]), len(src_data))
        server.add_stream('/test/source', src, src_info, src_data)

        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'data', 'read', '/test/source'])
        self.assertEqual(result.exit_code, 0)
        output = result.output.split('\n')
        for x in range(len(src_data)):
            row = src_data[x]
            expected = "%d %s" % (row['timestamp'], ' '.join('%f' % x for x in row['data']))
            self.assertTrue(expected in output[x])
        self.stop_server()

    def test_when_server_is_not_available(self):
        url = "http://127.0.0.1:%d" % unused_port()
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'data', 'read', '/test/source'])
        self.assertTrue('Error' in result.output)
        # self.assertEqual(result.exit_code, 1)

    @unittest.skip("TODO")
    def test_when_server_returns_invalid_data(self):
        server = FakeJoule()
        server.stream_list_response = "notjson"
        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'data', 'read', '/test/source'])
        self.assertTrue('Error' in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()

    @unittest.skip("TODO")
    def test_when_server_returns_error_code(self):
        server = FakeJoule()
        error_msg = "test error"
        error_code = 500
        server.stream_list_response = error_msg
        server.stream_list_code = error_code
        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'data', 'read', '/test/source'])
        self.assertTrue('%d' % error_code in result.output)
        self.assertTrue(error_msg in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()
