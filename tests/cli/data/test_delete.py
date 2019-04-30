import warnings
from aiohttp.test_utils import unused_port
import dateparser
from click.testing import CliRunner
from ..fake_joule import FakeJoule, FakeJouleTestCase
from joule.cli import main

warnings.simplefilter('always')


class TestDelete(FakeJouleTestCase):

    def test_data_delete(self):
        server = FakeJoule()
        self.start_server(server)
        runner = CliRunner()
        start_str = "20 January 2015 12:00"
        end_str = "1 hour ago"
        result = runner.invoke(main, ['data', 'delete',
                                      '/folder/src',
                                      '--start', start_str,
                                      '--end', end_str])
        self.assertEqual(result.exit_code, 0)
        (path, start, end) = self.msgs.get()
        self.assertEqual(path, '/folder/src')
        self.assertEqual(int(start), int(dateparser.parse(start_str).timestamp() * 1e6))
        # the relative time argument should grow
        self.assertLess(int(end), int(dateparser.parse(end_str).timestamp() * 1e6))
        self.stop_server()

    def test_when_stream_does_not_exist(self):
        server = FakeJoule()
        server.response = "stream does not exist"
        server.http_code = 404
        server.stub_data_delete = True
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['data', 'delete', '/folder/src'])
        self.assertTrue("Error" in result.output)
        self.stop_server()

    def test_when_server_returns_error_code(self):
        server = FakeJoule()
        server.response = "test error"
        server.http_code = 500
        server.stub_data_delete = True
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['data', 'delete', '/folder/src'])
        self.assertTrue('500' in result.output)
        self.assertTrue("test error" in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()
