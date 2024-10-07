import unittest
from unittest import mock
import tempfile
import shutil
import os
import asyncio

from joule.api import helpers, TcpNode
from joule import errors
from joule.constants import ConfigFiles

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
        default_file = os.path.join(self.temp_dir.name, ConfigFiles.default_node)

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
        node2 = helpers.get_node()
        self.assertEqual(node2.name, "node2")
        helpers.set_default_node("node1")
        default_node = helpers.get_node()
        self.assertEqual(default_node.name, "node1")
        # can set the default node by object
        helpers.set_default_node(node2)
        default_node = helpers.get_node()
        self.assertEqual(default_node.name, "node2")
        # may not set the default node to an empty string
        with self.assertRaises(errors.ApiError) as e:
            helpers.set_default_node("")
        self.assertIn("may not be empty", str(e.exception))
        # all nodes can be retrieved
        nodes = helpers.get_nodes()
        self.assertEqual(len(nodes), 2)
        self.assertIn(nodes[0].name, ["node1", "node2"])
        self.assertIn(nodes[1].name, ["node1", "node2"])

    def test_error_conditions_on_basic_operations(self):
        # cannot use a node that does not exist
        with self.assertRaises(errors.ApiError) as e:
            helpers.get_node("does_not_exist")
        self.assertIn("does_not_exist", str(e.exception))
        self.assertIn("not available", str(e.exception))
        with self.assertRaises(errors.ApiError):
            helpers.set_default_node("does_not_exist")
        # if no nodes are available
        with self.assertRaises(errors.ApiError):
            helpers.get_node()
        # if the config file is corrupt
        with open(os.path.join(self.temp_dir.name, ConfigFiles.nodes), "w") as f:
            f.write("invalid_json")
        with self.assertRaises(errors.ApiError) as e:
            helpers.get_node()
        self.assertIn("fix syntax", str(e.exception))
        # if no node configuration location can be found
        os.environ.pop("JOULE_USER_CONFIG_DIR", None)
        os.environ.pop("HOME", None)
        os.environ.pop("APPDATA", None)
        with self.assertRaises(errors.ApiError):
            helpers.get_node()

    @mock.patch('joule.api.helpers.chown')
    def test_fixes_config_ownership(self, mock_chown):
        # when run as root, revert ownership to the user
        os.environ["SUDO_USER"]='1'
        UID = 9898
        GID = 9899
        os.environ["SUDO_UID"]=str(UID)
        os.environ["SUDO_GID"]=str(GID)
        node1 = TcpNode("node1", "https://localhost:8088",
                        "node1_key")
        helpers.save_node(node1)
        default_node = helpers.get_node()
        self.assertEqual(default_node.name, "node1")
        # make sure all of the paths are chowned correctly
        calls = [mock.call(os.path.join(self.temp_dir.name), UID, GID),
                 mock.call(os.path.join(self.temp_dir.name, ConfigFiles.nodes), UID, GID),
                 mock.call(os.path.join(self.temp_dir.name, ConfigFiles.default_node), UID, GID)]
        self.assertEqual(len(mock_chown.call_args_list), 3)
        for call_item in mock_chown.call_args_list:
            self.assertIn(call_item, calls)

        # revert environment
        os.environ.pop("SUDO_USER")

    def test_uses_correct_config_file(self):
        # follows a preference of JOULE_USER_CONFIG_DIR, HOME, APPDATA
        # when looking for configurations
        saved_environ = os.environ.copy()
        for env_var in ["JOULE_USER_CONFIG_DIR", "HOME", "APPDATA"]:
            os.environ.pop(env_var, None)
        # check in reverse preference order
        for env_var in ["APPDATA","HOME","JOULE_USER_CONFIG_DIR"]:
            with tempfile.TemporaryDirectory() as tempdir:
                os.environ[env_var] = tempdir
                #the config directory is .joule unless it is directly specified
                if env_var in ["HOME", "APPDATA"]:
                    expected_config_dir = os.path.join(tempdir, '.joule')
                else:
                    expected_config_dir = tempdir
                self.assertEqual(helpers._user_config_dir(), expected_config_dir)
                self.assertTrue(os.path.isdir(expected_config_dir))
        # restore environment
        os.environ = saved_environ

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
