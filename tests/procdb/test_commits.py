import unittest
from . import helpers
import tempfile
import os
from joule.procdb import client


class TestCommits(unittest.TestCase):

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(delete=False).name

    def tearDown(self):
        os.remove(self.tmpfile)

    def test_commits_data(self):
        m = helpers.build_module(name="test",
                                 destination_paths={'path1': "/some/path/1"},
                                 source_paths={'path2': "/some/path/2"})
        s1 = helpers.build_stream(name="s1", path="/some/path/1")
        s2 = helpers.build_stream(name="s2", path="/some/path/2")

        procdb = client.SQLClient(self.tmpfile, max_log_lines=100)
        procdb._initialize_procdb()  # force initialization
        procdb.register_stream(s1)
        procdb.register_stream(s2)
        procdb.register_module(m)
        procdb.commit()

        procdb2 = client.SQLClient(self.tmpfile, max_log_lines=100)
        m_r = procdb2.find_module_by_id(m.id)
        self.assertEqual(m, m_r)
