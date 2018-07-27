from click.testing import CliRunner
import os
import signal
import multiprocessing
from aiohttp.test_utils import unused_port
import warnings
import time
from ..fake_joule import FakeJoule, FakeJouleTestCase
from joule.cli import main
from tests import helpers

STREAM_LIST = os.path.join(os.path.dirname(__file__), 'streams.json')
warnings.simplefilter('always')


class TestStreamList(FakeJouleTestCase):

    def test_lists_streams(self):
        server = FakeJoule()
        with open(STREAM_LIST, 'r') as f:
            server.response = f.read()
        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'stream', 'list'])
        self.assertEqual(result.exit_code, 0)
        output = result.output
        # make sure the folders are listed
        for folder in ['folder_1', 'folder_2', 'folder_3', 'folder_3_1', 'folder_4', 'folder_4_1']:
            self.assertTrue(folder in output)
        # make sure the streams are listed
        for stream in ['stream_1_1', 'stream_1_2', 'stream_2_1', 'stream_3_1_1']:
            self.assertTrue(stream in output)
        self.stop_server()

    def test_when_server_is_not_available(self):
        url = "http://127.0.0.1:%d" % unused_port()
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'stream', 'list'])
        self.assertTrue('Error' in result.output)
        self.assertEqual(result.exit_code, 1)

    def test_when_server_returns_invalid_data(self):
        server = FakeJoule()
        server.response = "notjson"
        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'stream', 'list'])
        self.assertTrue('Error' in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()

    def test_when_server_returns_error_code(self):
        server = FakeJoule()
        error_msg = "test error"
        error_code = 500
        server.response = error_msg
        server.http_code = error_code
        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'stream', 'list'])
        self.assertTrue('%d' % error_code in result.output)
        self.assertTrue(error_msg in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()