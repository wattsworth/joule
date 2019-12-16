from click.testing import CliRunner
import os
import warnings
from .fake_joule import FakeJoule, FakeJouleTestCase
from joule.cli import main

VERSION_JSON = os.path.join(os.path.dirname(__file__), 'version.json')
DBINFO_JSON = os.path.join(os.path.dirname(__file__), 'dbinfo.json')

warnings.simplefilter('always')


class TestInfo(FakeJouleTestCase):

    def test_joule_info(self):
        server = FakeJoule()
        with open(VERSION_JSON, 'r') as f:
            server.response = f.read()
        with open(DBINFO_JSON, 'r') as f:
            server.dbinfo_response = f.read()
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['node', 'info'])
        self.assertEqual(result.exit_code, 0)
        output = result.output
        # make sure the version is displayed
        self.assertIn("0.8.2", output)
        self.stop_server()
