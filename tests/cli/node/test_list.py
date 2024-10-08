from click.testing import CliRunner
from tests.cli.fake_joule import FakeJouleTestCase
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

class TestNodeList(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        os.environ["JOULE_USER_CONFIG_DIR"] = self.temp_dir.name
        self.ca_path = os.path.join(self.temp_dir.name, "ca.crt")
        shutil.copyfile(CAFILE, self.ca_path)
        
    def tearDown(self):
        self.temp_dir.cleanup()

    def test_lists_nodes(self):
        node1 = TcpNode("node1", "https://localhost:8088",
                        "node1_key")
        node2 = TcpNode("node2", "https://localhost:8089",
                        "node2_key")

        helpers.save_node(node1)
        helpers.save_node(node2)
        runner = CliRunner()
        result = runner.invoke(main, ['node', 'list'])
        print_result_on_error(result)
        self.assertEqual(result.exit_code, 0)
        output = result.output
        # make sure nodes are listed
        for name in ['node1', 'node2']:
            self.assertIn(name, output)

    @patch('joule.cli.node.list.get_node')
    @patch('joule.cli.node.list.get_nodes')
    def test_handles_api_error(self, get_nodes, get_node):
        get_node.side_effect = ApiError("test error")
        runner = CliRunner()
        result = runner.invoke(main, ['node', 'list'])
        self.assertIn('test error', result.output)
        self.assertEqual(result.exit_code, 1)
        
