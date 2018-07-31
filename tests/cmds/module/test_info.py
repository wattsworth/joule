import unittest
from click.testing import CliRunner
import os
import signal
import multiprocessing
from aiohttp.test_utils import unused_port
import warnings
import time
import json
import copy
import asyncio

from ..fake_joule import FakeJoule
from joule.cli import main

MODULE_INFO = os.path.join(os.path.dirname(__file__), 'module.json')
warnings.simplefilter('always')


class TestModuleInfo(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        self.loop.set_debug(True)
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        closed = self.loop.is_closed()
        if not closed:
            self.loop.call_soon(self.loop.stop)
            self.loop.run_forever()
            self.loop.close()
        asyncio.set_event_loop(None)

    def start_server(self, server):
        port = unused_port()
        self.msgs = multiprocessing.Queue()
        self.server_proc = multiprocessing.Process(target=server.start, args=(port, self.msgs))
        self.server_proc.start()
        time.sleep(0.01)
        return "http://localhost:%d" % port

    def stop_server(self):
        if self.server_proc is None:
            return
        # aiohttp doesn't always quit with SIGTERM
        os.kill(self.server_proc.pid, signal.SIGKILL)
        # join any zombies
        multiprocessing.active_children()
        self.server_proc.join()

    def test_shows_module_info(self):
        server = FakeJoule()
        with open(MODULE_INFO, 'r') as f:
            server.response = f.read()
        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'module', 'info', 'ModuleName'])
        self.assertEqual(result.exit_code, 0)
        # make sure stream inputs and outputs are listed
        output = result.output.split('\n')
        input_line = [x for x in output if 'my_input' in x][0]
        self.assertTrue("/folder_1/random" in input_line)
        output_line = [x for x in output if 'my_output' in x][0]
        self.assertTrue("/folder_1/filtered" in output_line)
        # check for name and description
        self.assertTrue('ModuleName' in result.output)
        self.assertTrue('the module description' in result.output)
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
            url = self.start_server(server)
            runner = CliRunner()
            result = runner.invoke(main, ['--url', url, 'module', 'info', 'ModuleName'])
            # just make sure different configurations do not cause errors in the output
            self.assertEqual(result.exit_code, 0)
            self.stop_server()

    def test_when_module_does_not_exist(self):
        server = FakeJoule()
        server.response = "module does not exist"
        server.http_code = 404
        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'module', 'info', 'ModuleName'])
        self.assertTrue("Error" in result.output)
        self.stop_server()

    def test_when_server_is_not_available(self):
        url = "http://127.0.0.1:%d" % unused_port()
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'module', 'info', 'ModuleName'])
        self.assertTrue('Error' in result.output)
        self.assertEqual(result.exit_code, 1)

    def test_when_server_returns_invalid_data(self):
        server = FakeJoule()
        server.response = "notjson"
        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'module', 'info', 'ModuleName'])
        self.assertTrue('Error' in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()

    def test_when_server_returns_error_code(self):
        server = FakeJoule()
        server.response = "test error"
        server.http_code = 500
        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'module', 'info', 'ModuleName'])
        self.assertTrue('500' in result.output)
        self.assertTrue("test error" in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()
