from click.testing import CliRunner
import os
import warnings

from ..fake_joule import FakeJoule, FakeJouleTestCase
from joule.cli import main

STREAM_INFO = os.path.join(os.path.dirname(__file__), 'stream.json')
warnings.simplefilter('always')


class TestStreamDestroy(FakeJouleTestCase):
    def test_destroys_stream(self):
        server = FakeJoule()
        url = self.start_server(server)
        runner = CliRunner()
        # does not delete with out confirmation
        result = runner.invoke(main,
                               ['--url', url, 'stream', 'destroy',
                                '/folder/stream'],
                               input='\n')
        self.assertTrue(self.msgs.empty())

        # executes deletes with confirmation
        result = runner.invoke(main,
                               ['--url', url, 'stream', 'destroy',
                                '/folder/stream'],
                               input='y\n')
        self.assertEqual(result.exit_code, 0)
        deleted_stream = self.msgs.get()
        self.assertEqual(deleted_stream, '/folder/stream')
        self.stop_server()