from click.testing import CliRunner
import os
import warnings

from ..fake_joule import FakeJoule, FakeJouleTestCase
from joule.cli import main

STREAM_INFO = os.path.join(os.path.dirname(__file__), 'stream.json')
warnings.simplefilter('always')


class TestFolderDestroy(FakeJouleTestCase):
    def test_destroys_folder(self):
        server = FakeJoule()
        url = self.start_server(server)
        runner = CliRunner()
        # deletes folders
        result = runner.invoke(main,
                               ['--url', url, 'folder', 'remove',
                                '/the/folder'])
        self.assertEqual(result.exit_code, 0)
        params = self.msgs.get()
        self.assertEqual(params['path'], '/the/folder')

        # recursively deletes folders
        result = runner.invoke(main,
                               ['--url', url, 'folder', 'remove',
                                '/the/folder', '-r'])
        self.assertEqual(result.exit_code, 0)
        params = self.msgs.get()
        self.assertEqual(params['path'], '/the/folder')
        self.assertTrue('recursive' in params)

        self.stop_server()

    def test_when_server_returns_error_code(self):
        server = FakeJoule()
        error_msg = "test error"
        error_code = 500
        server.response = error_msg
        server.http_code = error_code
        server.stub_folder_destroy = True
        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'folder', 'remove', '/the/folder'])
        self.assertTrue('%d' % error_code in result.output)
        self.assertTrue(error_msg in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()
