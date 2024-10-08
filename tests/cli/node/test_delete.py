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

class TestNodeDelete(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        os.environ["JOULE_USER_CONFIG_DIR"] = self.temp_dir.name
        self.ca_path = os.path.join(self.temp_dir.name, "ca.crt")
        shutil.copyfile(CAFILE, self.ca_path)
        
    def tearDown(self):
        self.temp_dir.cleanup()

    def test_deletes_node(self):
        node1 = TcpNode("node1", "https://localhost:8088",
                        "node1_key")
        node2 = TcpNode("node2", "https://localhost:8089",
                        "node2_key")

        helpers.save_node(node1)
        helpers.save_node(node2)
        runner = CliRunner()
        result = runner.invoke(main, ['node', 'delete','node2'])
        print_result_on_error(result)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("node2", result.output)
        # make sure only node1 is left
        nodes = helpers.get_nodes()
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].name, "node1")

    @patch('joule.cli.node.delete.delete_node')
    def test_handles_api_error(self, delete_node):
        delete_node.side_effect = ApiError("test error")
        runner = CliRunner()
        result = runner.invoke(main, ['node', 'delete','node2'])
        self.assertIn('test error', result.output)
        self.assertEqual(result.exit_code, 1)