import warnings
import os
from click.testing import CliRunner
from ..fake_joule import FakeJoule, FakeJouleTestCase
from joule.cli import main


STREAM_INFO = os.path.join(os.path.dirname(__file__), 'stream.json')
warnings.simplefilter('always')


class TestStreamRename(FakeJouleTestCase):

    def test_stream_rename(self):
        server = FakeJoule()
        with open(STREAM_INFO, 'r') as f:
            server.response = f.read()
        server.stub_stream_info = True  # use the response text
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['stream', 'rename', '/folder/src', 'new name'])
        self.assertEqual(result.exit_code, 0)
        stream_attrs = self.msgs.get()
        self.assertEqual(stream_attrs['name'], "new name")
        self.stop_server()

    def test_when_stream_does_not_exist(self):
        server = FakeJoule()
        server.response = "stream does not exist"
        server.http_code = 404
        server.stub_stream_rename = True
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['stream', 'rename', '/bad/path', 'new name'])
        self.assertIn("Error", result.output)
        self.stop_server()

    def test_when_server_returns_error_code(self):
        server = FakeJoule()
        server.response = "test error"
        server.http_code = 500
        server.stub_stream_info = True
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['stream', 'rename', '/folder/src', 'new name'])
        self.assertIn('500', result.output)
        self.assertIn("test error", result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()
