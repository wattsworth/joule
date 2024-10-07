from click.testing import CliRunner
import os
import warnings
import json
from tests.cli.fake_joule import FakeJoule, FakeJouleTestCase
from joule.models import Master
from joule.cli import main
from ..fake_joule import print_result_on_error



class TestMasterList(FakeJouleTestCase):

    def test_lists_masters(self):
        server = FakeJoule()
        masters = [Master(name="M1", type=Master.TYPE.USER, key="1234"),
                   Master(name="M2", type=Master.TYPE.JOULE_NODE, key="5678"),
                   Master(name="M3", type=Master.TYPE.LUMEN_NODE, key="abcd")]
        server.response = json.dumps([f.to_json() for f in masters])
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['master', 'list'])
        print_result_on_error(result)
        self.assertEqual(result.exit_code, 0)
        output = result.output
        # make sure all masters are listed
        for name in ['M1', 'M2', 'M3']:
            self.assertIn(name, output)
        # make sure keys are not present
        self.assertNotIn('1234', output)
        self.stop_server()

    def test_no_masters(self):
        server = FakeJoule()
        server.response = json.dumps([])
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['master', 'list'])
        print_result_on_error(result)
        self.assertEqual(result.exit_code, 0)
        # should have 3 None values in the output (no Users, Joule, or Lumen nodes)
        self.assertEqual(result.output.count("None"), 3)
        self.stop_server()

    def test_when_server_returns_error_code(self):
        server = FakeJoule()
        error_msg = "test error"
        error_code = 500
        server.response = error_msg
        server.http_code = error_code
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['master', 'list'])
        self.assertIn('%d' % error_code, result.output)
        self.assertIn(error_msg, result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()
