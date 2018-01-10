from joule.cmds.logs import LogsCmd
import unittest
from unittest import mock
import argparse


class TestLogs(unittest.TestCase):

    @mock.patch("joule.cmds.logs.procdb_client.SQLClient", autospec=True)
    @mock.patch("joule.cmds.logs.helpers.parse_config_file", autospec=True)
    def test_prints_logs(self, mock_load_configs, mock_client):
        my_procdb = mock_client.return_value
        my_procdb.find_module_by_name = mock.Mock()
        log_entries = ["entry %d" % x for x in range(4)]
        my_procdb.find_logs_by_module = mock.Mock(return_value=log_entries)

        mc = LogsCmd(mock.Mock(), mock.Mock())
        args = argparse.Namespace(config_file=None, module="test_module")

        with unittest.mock.patch('joule.cmds.logs.print') as mock_print:
            mc.take_action(args)
            for i in range(len(mock_print.call_args_list)):
                call = mock_print.call_args_list[i]
                self.assertRegex(call[0][0], log_entries[i])

    def test_accepts_config_file_parameter(self):
        lc = LogsCmd(mock.Mock(), mock.Mock())
        p = lc.get_parser("name")
        args = p.parse_args(["module_name", "--config-file=/config/file"])
        self.assertEqual(args.config_file, "/config/file")
        self.assertEqual(args.module, "module_name")
