from click.testing import CliRunner
import unittest
import asyncio
import warnings
from tests.cli.fake_joule import FakeJoule, FakeJouleTestCase
from joule.cli import main



class TestMasterAdd(FakeJouleTestCase):

    def test_add_user(self):
        server = FakeJoule()
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, "master add user johndoe".split(" "))
        output = result.output
        # make sure the username and key are printed
        self.assertIn("fakekey", output)
        self.assertIn("johndoe", output)
        # make sure the server got the right parameters
        params = self.msgs.get()
        self.assertEqual(params['identifier'], "johndoe")
        self.assertEqual(params['master_type'], "user")
        # make sure everything stops cleanly
        self.assertEqual(result.exit_code, 0)
        self.stop_server()

    def test_add_joule(self):
        server = FakeJoule()
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, "master add joule node1".split(" "))
        output = result.output
        # make sure the node name is printed
        self.assertIn("node1", output)
        # make sure the server got the right parameters
        params = self.msgs.get()
        self.assertEqual(params['identifier'], "node1")
        self.assertEqual(params['master_type'], "joule")
        # make sure everything stops cleanly
        self.assertEqual(result.exit_code, 0)
        self.stop_server()

    def test_add_lumen(self):
        server = FakeJoule()
        self.start_server(server)
        runner = CliRunner()
        # The first node joining a lumen requires a user
        result = runner.invoke(main, "master add lumen node1".split(" "),
                               input="John\nDoe\njohndoe@email.com\npassword\npassword")
        output = result.output
        # make sure the node name is printed
        self.assertIn("node1", output)
        # make sure the server got the right parameters
        params = self.msgs.get()
        self.assertEqual(params["first_name"], "John")
        self.assertEqual(params["last_name"], "Doe")
        self.assertEqual(params["email"], "johndoe@email.com")
        self.assertEqual(params["password"], "password")

        #loop = asyncio.new_event_loop()
        #asyncio.set_event_loop(loop)
        # Subsequent nodes need an auth key
        result = runner.invoke(main, "master add lumen node2".split(" "),
                               input="AC3412\n")
        # make sure the server got the right parameters
        params = self.msgs.get()
        self.assertEqual(params["auth_key"], "AC3412")
        output = result.output
        self.assertIn("node2", output)
        # make sure everything stops cleanly
        self.assertEqual(result.exit_code, 0)
        self.stop_server()

    def test_bad_arguments(self):
        runner = CliRunner()
        result = runner.invoke(main, ['master', 'add','invalid','node2'])
        self.assertIn('Error', result.output)
        self.assertEqual(result.exit_code, 2)

    def test_when_server_returns_invalid_data(self):
        server = FakeJoule()
        server.response = "notjson"
        server.stub_master = True
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, "master add user node2".split(" "))
        self.assertIn('Error', result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()

    def test_when_server_returns_error_code(self):
        server = FakeJoule()
        error_msg = "test error"
        error_code = 500
        server.response = error_msg
        server.http_code = error_code
        server.stub_master = True
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, "master add user node2".split(" "))
        self.assertIn(error_msg, result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()
