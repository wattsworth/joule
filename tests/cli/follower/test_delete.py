from click.testing import CliRunner
from tests.cli.fake_joule import FakeJoule, FakeJouleTestCase
from joule.cli import main
from ..fake_joule import print_result_on_error


class TestFollowerDelete(FakeJouleTestCase):

    def test_removes_followers(self):
        server = FakeJoule()
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['follower', 'delete','F1'])
        print_result_on_error(result)
        self.assertEqual(result.exit_code, 0)
        output = result.output
        # make sure follower is removed
        self.assertIn('F1', output)
        self.stop_server()


    def test_when_server_returns_error_code(self):
        server = FakeJoule()
        error_msg = "test error"
        error_code = 500
        server.response = error_msg
        server.http_code = error_code
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['follower', 'delete', 'F1'])
        self.assertIn('%d' % error_code, result.output)
        self.assertIn(error_msg, result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()
