from click.testing import CliRunner
from joule.cli import main
from ..fake_joule import print_result_on_error
import unittest
import tempfile
import shutil
import os
from joule.errors import ApiError
from unittest.mock import patch
from joule.api import helpers, TcpNode

CAFILE = os.path.join(os.path.dirname(__file__), 'ca.joule.crt')

class TestAddsNode(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        os.environ["JOULE_USER_CONFIG_DIR"] = self.temp_dir.name
        self.ca_path = os.path.join(self.temp_dir.name, "ca.crt")
        shutil.copyfile(CAFILE, self.ca_path)
        
    def tearDown(self):
        self.temp_dir.cleanup()

    def test_adds_node(self):
        node1 = TcpNode("node1", "https://localhost:8088",
                        "node1_key")
        node2 = TcpNode("node2", "https://localhost:8089",
                        "node2_key")

        helpers.save_node(node1)
        helpers.save_node(node2)

        # set node2 as default
        runner = CliRunner()
        result = runner.invoke(main, "node add node3 https://localhost:8090 node3_key".split(" "))
        print_result_on_error(result)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("node3", result.output)
        nodes = helpers.get_nodes()
        self.assertEqual(len(nodes), 3)
        self.assertEqual(nodes[2].name, "node3")
        self.assertEqual(nodes[2].url, "https://localhost:8090")

    @patch('joule.cli.node.add.save_node')
    def test_handles_api_error(self, save_node):
        save_node.side_effect = ApiError("test error")
        runner = CliRunner()
        result = runner.invoke(main, "node add node3 https://localhost:8090 node3_key".split(" "))
        self.assertIn('test error', result.output)
        self.assertEqual(result.exit_code, 1)

    @patch('joule.cli.node.add.utilities.misc.detect_url')
    def test_detects_url(self, detect_url):
        detect_url.return_value = "http://localhost:80"
        runner = CliRunner()
        result = runner.invoke(main, "node add node3 localhost node3_key".split(" "))
        print_result_on_error(result)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("node3", result.output)
        nodes = helpers.get_nodes()
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].name, "node3")
        self.assertEqual(nodes[0].url, "http://localhost:80")

    @patch('joule.cli.node.add.utilities.misc.detect_url')
    def test_handles_url_detection_error(self, detect_url):
        detect_url.return_value = None
        runner = CliRunner()
        result = runner.invoke(main, "node add node3 localhost node3_key".split(" "))
        self.assertEqual(result.exit_code, 1)
        self.assertIn("localhost", result.output)
        