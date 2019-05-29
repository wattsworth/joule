from click.testing import CliRunner
import os
import warnings
from tests.cli.fake_joule import FakeJoule, FakeJouleTestCase
from joule.cli import main

MODULE_LIST = os.path.join(os.path.dirname(__file__), 'modules.json')
warnings.simplefilter('always')


class TestModuleList(FakeJouleTestCase):

    def test_lists_modules(self):
        server = FakeJoule()
        with open(MODULE_LIST, 'r') as f:
            server.response = f.read()
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['module', 'list'])
        self.assertEqual(result.exit_code, 0)
        output = result.output
        # make sure modules are listed
        for name in ['Module%d' % x for x in range(1,5)]:
            self.assertTrue(name in output)
        # check a few streams
        for stream in ['folder_1/stream_1_1', '/folder_2/stream_2_1']:
            self.assertTrue(stream in output)
        self.stop_server()

    def test_when_server_returns_invalid_data(self):
        server = FakeJoule()
        server.response = "notjson"
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['module', 'list'])
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
        result = runner.invoke(main, ['module', 'list'])
        self.assertTrue('%d' % error_code in result.output)
        self.assertTrue(error_msg in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()
