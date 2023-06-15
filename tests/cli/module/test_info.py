from click.testing import CliRunner
import os
import asyncio

from aiohttp.test_utils import unused_port
import warnings
import json
import copy

from ..fake_joule import FakeJoule, FakeJouleTestCase
from joule.cli import main

MODULE_INFO = os.path.join(os.path.dirname(__file__), 'module.json')
warnings.simplefilter('always')


class TestModuleInfo(FakeJouleTestCase):

    def test_shows_module_info(self):
        server = FakeJoule()
        with open(MODULE_INFO, 'r') as f:
            server.response = f.read()
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['module', 'info', 'ModuleName'])
        self.assertEqual(result.exit_code, 0)
        # make sure stream inputs and outputs are listed
        self.assertIn("/folder_1/random", result.output)
        self.assertIn("/folder_1/filtered", result.output)
        # check for name and description
        self.assertIn('ModuleName', result.output)
        self.assertIn('the module description', result.output)
        self.stop_server()

    def test_handles_different_module_configurations(self):
        server = FakeJoule()
        with open(MODULE_INFO, 'r') as f:
            orig_model_data = json.loads(f.read())
        module1 = copy.deepcopy(orig_model_data)
        module1['inputs'] = []
        module2 = copy.deepcopy(orig_model_data)
        module2['outputs'] = []
        for module in [module1, module2]:

            server.response = json.dumps(module)

            self.start_server(server)
            runner = CliRunner()
            result = runner.invoke(main, ['module', 'info', 'ModuleName'])
            # just make sure different configurations do not cause errors in the output
            self.assertEqual(result.exit_code, 0)
            self.stop_server()

    def test_when_module_does_not_exist(self):
        server = FakeJoule()
        server.response = "module does not exist"
        server.http_code = 404
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['module', 'info', 'ModuleName'])
        self.assertTrue("Error" in result.output)
        self.stop_server()

    def test_when_server_returns_invalid_data(self):
        server = FakeJoule()
        server.response = "notjson"
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['module', 'info', 'ModuleName'])
        self.assertTrue('Error' in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()

    def test_when_server_returns_error_code(self):
        server = FakeJoule()
        server.response = "test error"
        server.http_code = 500
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['module', 'info', 'ModuleName'])
        self.assertTrue('500' in result.output)
        self.assertTrue("test error" in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()
