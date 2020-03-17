import warnings
import os
from click.testing import CliRunner
from ..fake_joule import FakeJoule, FakeJouleTestCase
from joule.cli import main


FOLDER_INFO = os.path.join(os.path.dirname(__file__), 'folder.json')
warnings.simplefilter('always')


class TestFolderRename(FakeJouleTestCase):

    def test_folder_rename(self):
        server = FakeJoule()
        with open(FOLDER_INFO, 'r') as f:
            server.response = f.read()
        server.stub_folder_info = True  # use the response text
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['folder', 'rename', '/folder/src', 'new name'])
        self.assertEqual(result.exit_code, 0)
        stream_attrs = self.msgs.get()
        self.assertEqual(stream_attrs['name'], "new name")
        self.stop_server()

    def test_when_folder_does_not_exist(self):
        server = FakeJoule()
        server.response = "folder does not exist"
        server.http_code = 404
        server.stub_folder_rename = True
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['folder', 'rename', '/bad/path', 'new name'])
        self.assertTrue("Error" in result.output)
        self.stop_server()

    def test_when_server_returns_error_code(self):
        server = FakeJoule()
        server.response = "test error"
        server.http_code = 500
        server.stub_folder_info = True
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['folder', 'rename', '/folder/src', 'new name'])
        self.assertTrue('500' in result.output)
        self.assertTrue("test error" in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()
