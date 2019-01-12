from click.testing import CliRunner
import unittest
import warnings

from ..fake_joule import FakeJoule, FakeJouleTestCase
from joule.cli import main

warnings.simplefilter('always')


class TestStreamDelete(FakeJouleTestCase):
    def test_deletes_stream(self):
        server = FakeJoule()
        url = self.start_server(server)
        runner = CliRunner()
        # does not delete with out confirmation
        result = runner.invoke(main,
                      ['--url', url, 'stream', 'delete',
                       '/folder/stream'],
                      input='\n')
        self.assertTrue(self.msgs.empty())

        # executes deletes with confirmation
        result = runner.invoke(main,
                               ['--url', url, 'stream', 'delete',
                                '/folder/stream'],
                               input='y\n')
        self.assertEqual(result.exit_code, 0)
        deleted_stream = self.msgs.get()
        self.assertEqual(deleted_stream, '/folder/stream')
        self.stop_server()

    def test_when_server_returns_error_code(self):
        server = FakeJoule()
        error_msg = "test error"
        error_code = 500
        server.response = error_msg
        server.http_code = error_code
        server.stub_stream_destroy = True
        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'stream', 'delete', '/folder/stream'],
                               input='y\n')
        self.assertTrue('%d' % error_code in result.output)
        self.assertTrue(error_msg in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()