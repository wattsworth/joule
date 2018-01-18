from joule.daemon import module
from joule.cmds.modules import ModulesCmd
from . import helpers
import unittest
from unittest import mock
import argparse
import os


FIELD_MODULE = 0
FIELD_SOURCES = 1
FIELD_DESTS = 2
FIELD_STATUS = 3
FIELD_MEM = 4
FIELD_CPU = 5


class TestModulesError(unittest.TestCase):

    def setUp(self):
        my_pid = os.getpid()
        self.m1 = helpers.build_module("m1",
                                       description="test m1",
                                       input_paths={},
                                       output_paths={"path1": "/m1/path/1",
                                                          "path2": "/m1/path/2"},
                                       status=module.STATUS_RUNNING,
                                       pid=my_pid)

        self.m2 = helpers.build_module("m2",
                                       description="",
                                       input_paths={"path1": "/m2/path/1",
                                                     "path2": "/m2/path/2"},
                                       output_paths={
                                           "path1": "/m2/path/3"},
                                       status=module.STATUS_RUNNING,
                                       pid=my_pid)

        self.my_modules = (self.m1, self.m2)

    @mock.patch("joule.cmds.modules.psutil", autospec=True)
    @mock.patch("joule.cmds.modules.procdb_client.SQLClient", autospec=True)
    @mock.patch("joule.cmds.helpers.parse_config_file", autospec=True)
    def test_sets_status_to_failed_on_get_info_exception(self, mock_parse_configs, mock_client, mock_psutil):
        my_procdb = mock_client.return_value
        my_procdb.find_all_modules = mock.Mock(return_value=self.my_modules)
        mock_psutil.Process = mock.Mock(sides_effect=Exception())

        mc = ModulesCmd(mock.Mock(), mock.Mock())
        args = argparse.Namespace(config_file=None, formatter=None)
        r = mc.take_action(args)

        module_data = r[1]

        for i in range(len(module_data)):
            # make sure status is [failed] and cpu and mem are nulled out
            self.assertEqual(
                module_data[i][FIELD_STATUS], module.STATUS_FAILED)
            self.assertEqual(module_data[i][FIELD_CPU], "--")
            self.assertEqual(module_data[i][FIELD_MEM], "--")
