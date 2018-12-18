import warnings
from aiohttp.test_utils import unused_port
from click.testing import CliRunner
from ..fake_joule import FakeJoule, FakeJouleTestCase
from joule.cli import main

warnings.simplefilter('always')


class TestFolderMove(FakeJouleTestCase):

    def test_folder_move(self):
        server = FakeJoule()
        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'folder', 'move', '/folder/src', '/folder/dest'])
        self.assertEqual(result.exit_code, 0)
        (path, destination) = self.msgs.get()
        self.assertEqual(path, '/folder/src')
        self.stop_server()

    def test_when_folder_does_not_exist(self):
        server = FakeJoule()
        server.response = "folder does not exist"
        server.http_code = 404
        server.stub_folder_move = True
        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'folder', 'move', '/bad/path', '/folder/dest'])
        self.assertTrue("Error" in result.output)
        self.stop_server()

    def test_when_server_is_not_available(self):
        url = "http://127.0.0.1:%d" % unused_port()
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'folder', 'move', '/folder/src', '/folder/dest'])
        self.assertTrue('Error' in result.output)
        self.assertEqual(result.exit_code, 1)

    def test_when_server_returns_invalid_data(self):
        server = FakeJoule()
        server.response = "notjson"
        server.stub_folder_move = True
        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'folder', 'move', '/folder/src', '/folder/dest'])
        self.assertTrue('Error' in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()

    def test_when_server_returns_error_code(self):
        server = FakeJoule()
        server.response = "test error"
        server.http_code = 500
        server.stub_folder_move = True
        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'folder', 'move', '/folder/src', '/folder/dest'])
        self.assertTrue('500' in result.output)
        self.assertTrue("test error" in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()
