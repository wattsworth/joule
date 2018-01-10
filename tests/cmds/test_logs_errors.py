from joule.cmds.logs import LogsCmd
import unittest
from unittest import mock
import argparse


class TestLogs(unittest.TestCase):

    @mock.patch("joule.cmds.logs.procdb_client.SQLClient", autospec=True)
    @mock.patch("joule.cmds.logs.helpers.parse_config_file", autospec=True)
    def test_error_if_module_not_found(self, mock_load_configs, mock_client):
        """prints error message if module not found"""
        my_procdb = mock_client.return_value
        my_procdb.find_module_by_name = mock.Mock(return_value=None)

        lc = LogsCmd(mock.Mock(), mock.Mock())
        args = argparse.Namespace(config_file=None, module="missing_module")

        with unittest.mock.patch('joule.cmds.logs.print') as mock_print:
            lc.take_action(args)
            call = mock_print.call_args
            self.assertRegex(call[0][0], "missing_module")
            self.assertEqual(mock_print.call_count, 1)

    @mock.patch("joule.cmds.logs.procdb_client.SQLClient", autospec=True)
    @mock.patch("joule.cmds.logs.helpers.parse_config_file", autospec=True)
    def test_notifies_if_empty_log(self, mock_load_configs, mock_client):
        """prints message if the module doesn't have any logs"""
        my_procdb = mock_client.return_value
        # the module exists..
        my_procdb.find_module_by_name = mock.Mock()
        #..but it doesn't have any log entries
        my_procdb.find_logs_by_module = mock.Mock(return_value=[])

        lc = LogsCmd(mock.Mock(), mock.Mock())
        args = argparse.Namespace(config_file=None, module="nolog_module")

        with unittest.mock.patch('joule.cmds.logs.print') as mock_print:
            lc.take_action(args)
            call = mock_print.call_args
            self.assertRegex(call[0][0], "empty")
            self.assertEqual(mock_print.call_count, 1)
