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


class TestDataCopy(unittest.TestCase):

    def start_server(self, server):
        port = unused_port()
        self.server_proc = multiprocessing.Process(target=server.start, args=(port,))
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

    def test_copies_data(self):
        server = FakeJoule()
        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'data', 'copy', '/test/source', '/test/destination'])
        output = result.output
        print(output)
        self.stop_server()

    def test_when_server_is_not_available(self):
        url = "http://127.0.0.1:%d" % unused_port()
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'data', 'copy'])
        self.assertTrue('Error' in result.output)
        # self.assertEqual(result.exit_code, 1)

    @unittest.skip("TODO")
    def test_when_server_returns_invalid_data(self):
        server = FakeJoule()
        server.stream_list_response = "notjson"
        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'data', 'copy'])
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
        result = runner.invoke(main, ['--url', url, 'stream', 'list'])
        self.assertTrue('%d' % error_code in result.output)
        self.assertTrue(error_msg in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()
