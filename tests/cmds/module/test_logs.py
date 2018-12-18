from click.testing import CliRunner
import os
from aiohttp.test_utils import unused_port
import warnings
from ..fake_joule import FakeJoule, FakeJouleTestCase
from joule.cli import main

MODULE_LOGS = os.path.join(os.path.dirname(__file__), 'logs.json')
warnings.simplefilter('always')


class TestModuleLogs(FakeJouleTestCase):

    def test_print_module_logs(self):
        server = FakeJoule()
        with open(MODULE_LOGS, 'r') as f:
            server.response = f.read()
        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'module', 'logs','my_module'])
        self.assertEqual(result.exit_code, 0)
        output = result.output
        self.assertTrue(len(output)>0)
        self.assertTrue("starting" in output)
        self.stop_server()

    def test_when_server_is_not_available(self):
        url = "http://127.0.0.1:%d" % unused_port()
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'module', 'logs', 'my_module'])
        self.assertTrue('Error' in result.output)
        self.assertEqual(result.exit_code, 1)

    def test_when_server_returns_invalid_data(self):
        server = FakeJoule()
        server.response = "notjson"
        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'module', 'logs', 'my_module'])
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
        result = runner.invoke(main, ['--url', url, 'module', 'logs', 'my_module'])
        self.assertTrue('%d' % error_code in result.output)
        self.assertTrue(error_msg in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()
