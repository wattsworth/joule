from click.testing import CliRunner
import os
import logging

import warnings
from tests.cli.fake_joule import FakeJoule, FakeJouleTestCase
from joule.cli import main


STREAM_LIST = os.path.join(os.path.dirname(__file__), 'streams.json')
warnings.simplefilter('always')
aio_log = logging.getLogger('aiohttp.access')
aio_log.setLevel(logging.WARNING)


class TestStreamList(FakeJouleTestCase):

    def test_lists_streams(self):
        server = FakeJoule()
        with open(STREAM_LIST, 'r') as f:
            server.response = f.read()
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['stream', 'list'])
        self.assertEqual(result.exit_code, 0)
        output = result.output
        # make sure the folders are listed
        for folder in ['archive', 'live']:
            self.assertTrue(folder in output)
        # make sure the streams are listed
        for stream in ['data1', 'data2', 'base', 'plus1']:
            self.assertTrue(stream in output)
        # should not have Legend or layout strings
        self.assertFalse("Legend" in output)
        # check for layout strings
        self.assertFalse("int32_1" in output)
        self.stop_server()

    def test_lists_streams_with_options(self):
        server = FakeJoule()
        with open(STREAM_LIST, 'r') as f:
            server.response = f.read()
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['stream', 'list', '-s', '-l'])
        self.assertEqual(result.exit_code, 0)
        output = result.output
        # check for the legend
        self.assertTrue("Legend" in output)
        # check for layout strings
        self.assertTrue("int32_1" in output)
        self.stop_server()

    def test_when_server_returns_invalid_data(self):
        server = FakeJoule()
        server.response = "notjson"
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['stream', 'list'])
        self.assertTrue('Error' in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()

    def test_when_server_returns_error_code(self):
        server = FakeJoule()
        error_msg = "test error"
        error_code = 500
        server.response = error_msg
        server.http_code = error_code
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['stream', 'list'])
        self.assertTrue('%d' % error_code in result.output)
        self.assertTrue(error_msg in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()
