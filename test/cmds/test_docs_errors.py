
import unittest
from unittest import mock
from joule.cmds import docs


class TestDocs(unittest.TestCase):

    def setUp(self):
        self.my_docs = docs.DocsCmd(mock.Mock(), mock.Mock())
        self.doc_json = [{"name": "m1",
                          "description": "first module"},
                         {"name": "m2",
                          "description": "second module"}]
        
    def test_cannot_add_module_twice(self):
        existing_item = {"name": "m1",
                         "description": "a repeat"}
        with self.assertRaisesRegex(Exception,
                                    "already documented"):
            self.my_docs.insert_doc(self.doc_json, existing_item)
        self.assertEqual(len(self.doc_json), 2)

    def test_cannot_remove_undocumented_module(self):
        with self.assertRaisesRegex(Exception, "not documented"):
            self.my_docs.remove_doc(self.doc_json, "m3")

    def test_must_have_required_keys(self):
        with self.assertRaisesRegex(Exception, "required"):
            self.my_docs.validate_doc({"name": "missing keys"})

    def test_cannot_update_undocumented_module(self):
        new_item = {"name": "m3",
                    "description": "new module"}
        with self.assertRaisesRegex(Exception,
                                    "not documented"):
            self.my_docs.update_doc(self.doc_json, new_item)
        self.assertEqual(len(self.doc_json), 2)
        pass
    
