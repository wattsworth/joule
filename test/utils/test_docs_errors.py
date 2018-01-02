
import unittest
from unittest import mock
from joule.cmds import docs


class TestDocs(unittest.TestCase):

    def test_error_on_bad_exec_cmd(self):
        my_docs = docs.DocsCmd(mock.Mock(), mock.Mock())
        res = my_docs.get_help_output("cmd_does_not_exist")
        print(res)

