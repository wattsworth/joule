from joule.daemon import module
from joule.cmds.modules import ModulesCmd
from . import helpers
import unittest
from unittest import mock
import argparse
import os
import functools

FIELD_MODULE = 0
FIELD_SOURCES = 1
FIELD_DESTS = 2


class TestModules(unittest.TestCase):

    def setUp(self):
        my_pid = os.getpid()
        self.m1 = helpers.build_module("m1",
                                       description="test m1",
                                       source_paths={},
                                       destination_paths={"path1": "/m1/path/1",
                                                          "path2": "/m1/path/2"},
                                       status=module.STATUS_RUNNING,
                                       pid=my_pid)

        self.m2 = helpers.build_module("m2",
                                       description="",
                                       source_paths={"path1": "/m2/path/1",
                                                     "path2": "/m2/path/2"},
                                       destination_paths={
                                           "path1": "/m2/path/3"},
                                       status=module.STATUS_RUNNING,
                                       pid=my_pid)

        self.my_modules = (self.m1, self.m2)

    @mock.patch("joule.cmds.modules.psutil", autospec=True)
    @mock.patch("joule.cmds.modules.procdb_client.SQLClient", autospec=True)
    @mock.patch("joule.cmds.helpers.parse_config_file", autospec=True)
    def test_displays_json_format(self, mock_parse_configs, mock_client, mock_psutil):
        my_procdb = mock_client.return_value
        my_procdb.find_all_modules = mock.Mock(return_value=self.my_modules)

        mc = ModulesCmd(mock.Mock(), mock.Mock())

        args = argparse.Namespace(config_file=None, formatter="json")
        r = mc.take_action(args)
        module_data = r[1]

        for i in range(len(module_data)):
            # verify module field is a name|description dict
            self.assertTrue('name' in module_data[i][FIELD_MODULE])
            self.assertTrue('description' in module_data[i][FIELD_MODULE])
            # verify sources and destinations are arrays of path names
            sources = list(self.my_modules[i].source_paths.values())
            dests = list(self.my_modules[i].destination_paths.values())
            self.assertEqual(module_data[i][FIELD_SOURCES], sources)
            self.assertEqual(module_data[i][FIELD_DESTS], dests)

    @mock.patch("joule.cmds.modules.psutil", autospec=True)
    @mock.patch("joule.cmds.modules.procdb_client.SQLClient", autospec=True)
    @mock.patch("joule.cmds.helpers.parse_config_file", autospec=True)
    def test_displays_text_format(self, mock_parse_configs, mock_client, mock_psutil):
        my_procdb = mock_client.return_value
        my_procdb.find_all_modules = mock.Mock(return_value=self.my_modules)

        mc = ModulesCmd(mock.Mock(), mock.Mock())

        args = argparse.Namespace(config_file=None, formatter=None)
        r = mc.take_action(args)
        module_data = r[1]

        for i in range(len(module_data)):
            # verify module field is string with name and description
            self.assertRegex(
                module_data[i][FIELD_MODULE], self.my_modules[i].name)
            if(self.my_modules[i].description != ""):
                self.assertRegex(
                    module_data[i][FIELD_MODULE], self.my_modules[i].description)
            # verify sources and destinations are strings with path names
            sources = list(self.my_modules[i].source_paths.values())
            dests = list(self.my_modules[i].destination_paths.values())
            for source in sources:
                self.assertRegex(module_data[i][FIELD_SOURCES], source)
            for dest in dests:
                self.assertRegex(module_data[i][FIELD_DESTS], dest)

    def test_accepts_config_file_parameter(self):
        mc = ModulesCmd(mock.Mock(), mock.Mock())
        p = mc.get_parser("name")
        args = p.parse_args(["--config-file=/config/file"])
        self.assertTrue(args.config_file, "/config/file")
