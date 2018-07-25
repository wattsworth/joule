import unittest
from click.testing import CliRunner
import os
import signal
import multiprocessing
from aiohttp.test_utils import unused_port
import warnings

from ..fake_joule import FakeJoule
from joule.cli import main

STREAM_LIST = os.path.join(os.path.dirname(__file__), 'streams.json')
warnings.simplefilter('always')


class TestStreamList(unittest.TestCase):

    def start_server(self, server):
        port = unused_port()
        self.msgs = multiprocessing.Queue()
        self.server_proc = multiprocessing.Process(target=server.start, args=(port, self.msgs))
        self.server_proc.start()
        return "http://localhost:%d" % port

    def stop_server(self):
        if self.server_proc is None:
            return
        # aiohttp doesn't always quit with SIGTERM
        os.kill(self.server_proc.pid, signal.SIGKILL)
        # join any zombies
        multiprocessing.active_children()
        self.server_proc.join()

    def test_lists_streams(self):
        server = FakeJoule()
        with open(STREAM_LIST, 'r') as f:
            server.stream_list_response = f.read()
        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'stream', 'list'])
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
        server.stream_list_response = "notjson"
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
        server.stream_list_response = error_msg
        server.stream_list_code = error_code
        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'stream', 'list'])
        self.assertTrue('%d' % error_code in result.output)
        self.assertTrue(error_msg in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()
