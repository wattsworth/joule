from tests.api import mock_session
import unittest
import tempfile
import shutil
import os
import asyncio

from joule.api import helpers, TcpNode
from joule import errors

CAFILE = os.path.join(os.path.dirname(__file__), 'ca.joule.crt')


class TestApiHelpers(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        os.environ["JOULE_USER_CONFIG_DIR"] = self.temp_dir.name
        self.ca_path = os.path.join(self.temp_dir.name, "ca.crt")
        shutil.copyfile(CAFILE, self.ca_path)
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.temp_dir.cleanup()
        self.loop.close()

    def test_creates_config_dir(self):
        # require helper to create the directory
        config_dir = os.path.join(self.temp_dir.name, "configs")
        os.environ["JOULE_USER_CONFIG_DIR"] = config_dir
        helpers.get_nodes()
        self.assertTrue(os.path.isdir(config_dir))

    def test_normal_operation(self):
        node1 = TcpNode("node1", "https://localhost:8088",
                        "node1_key")
        node2 = TcpNode("node2", "https://localhost:8089",
                        "node2_key")
        default_file = os.path.join(self.temp_dir.name, "default_node.txt")

        helpers.save_node(node1)
        helpers.save_node(node2)
        default_node = helpers.get_node()
        # first node should be the default
        self.assertEqual(node1.name, default_node.name)
        # nodes should use the cafile
        self.assertEqual(default_node.session.cafile, self.ca_path)
        # unless it is missing...
        os.remove(self.ca_path)
        retrieved_node2 = helpers.get_node("node2")
        # then nodes do not have a cafile set
        self.assertEqual(retrieved_node2.session.cafile, "")
        self.assertEqual(retrieved_node2.url, node2.url)
        # when the default node is deleted, the next one becomes the default
        helpers.delete_node(node1)
        default_node = helpers.get_node()
        self.assertEqual(default_node.name, "node2")
        # if the default file is missing it is automatically created
        os.remove(default_file)
        default_node = helpers.get_node()
        self.assertEqual(default_node.name, "node2")
        self.assertTrue(os.path.isfile(default_file))
        # but the default can be changed when the node is added back
        helpers.save_node(node1)
        default_node = helpers.get_node()
        self.assertEqual(default_node.name, "node2")
        helpers.set_default_node("node1")
        default_node = helpers.get_node()
        self.assertEqual(default_node.name, "node1")
        # all nodes can be retrieved
        nodes = helpers.get_nodes()
        self.assertEqual(len(nodes), 2)
        self.assertTrue(nodes[0].name in ["node1", "node2"])
        self.assertTrue(nodes[1].name in ["node1", "node2"])

    def test_lists_all_nodes(self):
        pass

    def test_delete_node(self):
        # nodes can be deleted by object or name
        node1 = TcpNode("node1", "https://localhost:8088",
                        "node1_key")
        node2 = TcpNode("node2", "https://localhost:8089",
                        "node2_key")
        helpers.save_node(node1)
        helpers.save_node(node2)
        self.assertEqual(len(helpers.get_nodes()), 2)
        helpers.delete_node(node1)
        helpers.delete_node("node2")

        # removing a non-existent node generates an error
        with self.assertRaises(errors.ApiError):
            helpers.delete_node(node1)


    def test_save_node(self):
        pass
