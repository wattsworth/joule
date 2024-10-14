from click.testing import CliRunner
import json
from tests.cli.fake_joule import FakeJoule, FakeJouleTestCase
from joule.models import Proxy
from joule.cli import main
from ..fake_joule import print_result_on_error


class TestFollowerList(FakeJouleTestCase):

    def test_proxy_info(self):
        server = FakeJoule()
        proxy = Proxy(name="P1", uuid=4,url="http://127.0.0.1:8080")
        server.response = json.dumps(proxy.to_json())
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['proxy', 'info','P1'])
        print_result_on_error(result)
        self.assertEqual(result.exit_code, 0)
        output = result.output
        # make sure info is listed
        self.assertIn('P1', output)
        self.assertIn('http://127.0.0.1:8080', output)
        self.assertIn('4', output)
        self.stop_server()

    def test_when_server_returns_error_code(self):
        server = FakeJoule()
        error_msg = "test error"
        error_code = 500
        server.response = error_msg
        server.http_code = error_code
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['proxy', 'info', 'P1'])
        self.assertIn('%d' % error_code, result.output)
        self.assertIn(error_msg, result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()
