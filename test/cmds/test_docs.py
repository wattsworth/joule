
import textwrap
import unittest
from unittest import mock
from contextlib import redirect_stdout
import io

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

    def test_applies_markdown_to_values(self):
        input = {}
        input["usage"] = textwrap.dedent(
            """

            | 1  | 2     |
            |----|-------|
            | I  | am    |
            | A  | table |

            """)
        input["stream_configs"] = textwrap.dedent(
            """
            input1
            :  [Main]
               key = value
               key2 = value2

            input2
            :  [Main]
               key = value
               key3 = value3
            """
        )
        result = self.my_docs.markdown_values(input)
        self.assertEqual(result["usage"], textwrap.dedent(
            """<table>
<thead>
<tr>
<th>1</th>
<th>2</th>
</tr>
</thead>
<tbody>
<tr>
<td>I</td>
<td>am</td>
</tr>
<tr>
<td>A</td>
<td>table</td>
</tr>
</tbody>
</table>"""))
        
    def test_inserts_new_modules(self):
        docs = [{"name": "m1",
                 "description": "first module"},
                {"name": "m2",
                 "description": "second module"}]
        new_item = {"name": "m3",
                    "description": "third module"}
        self.my_docs.insert_doc(docs, new_item)
        self.assertEqual(len(docs), 3)

    def test_updates_existing_modules(self):
        docs = [{"name": "m1",
                 "description": "first module"},
                {"name": "m2",
                 "description": "second module"}]
        new_item = {"name": "m2",
                    "description": "new value"}
        self.my_docs.update_doc(docs, new_item)
        self.assertEqual(len(docs), 2)
        self.assertEqual(docs[1]["description"], "new value")

    def test_lists_documented_module(self):
        docs = [{"name": "m1",
                 "description": "first module"},
                {"name": "m2",
                 "description": "second module"}]
        f = io.StringIO()
        with redirect_stdout(f):
            self.my_docs.list_docs(docs)
        self.assertEqual(len(f.getvalue().split('\n')), 4)

    def test_removes_modules(self):
        docs = [{"name": "m1",
                 "description": "first module"},
                {"name": "m2",
                 "description": "second module"}]
        self.my_docs.remove_doc(docs, "m2")
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["name"], "m1")

