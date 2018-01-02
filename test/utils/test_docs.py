
import unittest
from unittest import mock
from joule.cmds import docs


class TestDocs(unittest.TestCase):

    def setUp(self):
        self.my_docs = docs.DocsCmd(mock.Mock(), mock.Mock())
        
    def test_retrieves_module_help_output(self):
        res = self.my_docs.get_help_output("ps -f")
        self.assertTrue(len(res) > 0)

    def test_parses_help_output(self):
        output = """ This is the module output:
        ..some text before the help content..
        ---
        :name:
          Test Module
        :description:
          Some rather long text
        :usage:
          This one has
          multiple
             <lines>
        ---
        ..some text after the help content
        """
        desired_result = {
            "name": "Test Module",
            "description": "Some rather long text",
            "usage": "This one has\nmultiple\n   <lines>"
        }
        
        result = self.my_docs.parse_help_output(output)
        self.assertEqual(result, desired_result)


