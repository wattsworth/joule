from click.testing import CliRunner
import os
import warnings
import json
from tests.cli.fake_joule import FakeJoule, FakeJouleTestCase
from joule.models import Follower
from joule.cli import main
from ..fake_joule import print_result_on_error


class TestFollowerList(FakeJouleTestCase):

    def test_lists_followers(self):
        server = FakeJoule()
        followers = [Follower(name="F1",key="1234",location="site1"),
                     Follower(name="F2",key="5678",location="site2")]
        server.response = json.dumps([f.to_json() for f in followers])
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['follower', 'list'])
        print_result_on_error(result)
        self.assertEqual(result.exit_code, 0)
        output = result.output
        # make sure followers are listed
        for name in ['F1', 'F2']:
            self.assertIn(name, output)
        # make sure keys are not present
        self.assertNotIn('1234', output)
        self.stop_server()

    def test_no_followers(self):
        server = FakeJoule()
        server.response = json.dumps([])
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['follower', 'list'])
        print_result_on_error(result)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("This node cannot control any other nodes", result.output)
        self.stop_server()

    def test_when_server_returns_error_code(self):
        server = FakeJoule()
        error_msg = "test error"
        error_code = 500
        server.response = error_msg
        server.http_code = error_code
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['follower', 'list'])
        self.assertIn('%d' % error_code, result.output)
        self.assertIn(error_msg, result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()
