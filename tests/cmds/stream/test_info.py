import unittest
from click.testing import CliRunner
import os
import signal
import multiprocessing
from aiohttp.test_utils import unused_port
import warnings

from ..fake_joule import FakeJoule
from joule.cli import main

STREAM_INFO = os.path.join(os.path.dirname(__file__), 'stream.json')
warnings.simplefilter('always')


class TestStreamInfo(unittest.TestCase):

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

    def test_shows_stream_info(self):
        server = FakeJoule()
        with open(STREAM_INFO, 'r') as f:
            server.response = f.read()
        server.stub_stream_info = True  # use the response text
        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'stream', 'info', '/folder_1/random'])
        self.assertEqual(result.exit_code, 0)
        # make sure the items are populated correctly
        output = result.output.split('\n')
        row_line = [x for x in output if 'Rows' in x][0]
        self.assertTrue("73820" in row_line)
        start_line = [x for x in output if 'Start' in x][0]
        self.assertTrue("2018-07-11 14:50:44" in start_line)
        end_line = [x for x in output if 'End' in x][0]
        self.assertTrue("2018-07-25 11:52:56" in end_line)
        for element_name in ['x', 'y', 'z']:
            for line in output:
                if element_name in line:
                    break
            else:
                self.fail("element name %s not in output" % element_name)
        self.stop_server()

    def test_when_stream_does_not_exist(self):
        server = FakeJoule()
        server.response = "stream does not exist"
        server.http_code = 404
        server.stub_stream_info = True
        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'stream', 'info', '/bad/path'])
        self.assertTrue("Error" in result.output)
        self.stop_server()

    def test_when_server_is_not_available(self):
        url = "http://127.0.0.1:%d" % unused_port()
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'stream', 'info', '/folder/stream'])
        self.assertTrue('Error' in result.output)
        self.assertEqual(result.exit_code, 1)

    def test_when_server_returns_invalid_data(self):
        server = FakeJoule()
        server.response = "notjson"
        server.stub_stream_info = True
        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'stream', 'info', 'folder/stream'])
        self.assertTrue('Error' in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()

    def test_when_server_returns_error_code(self):
        server = FakeJoule()
        server.response = "test error"
        server.http_code = 500
        server.stub_stream_info = True
        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'stream', 'info', 'folder/stream'])
        self.assertTrue('500' in result.output)
        self.assertTrue("test error" in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()
