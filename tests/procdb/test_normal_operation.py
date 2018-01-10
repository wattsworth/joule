import unittest
from joule.procdb import client
from . import helpers
from joule.daemon import module


class TestNormalOperation(unittest.TestCase):
    """Streams and modules can be stored and retrieved"""
    
    def setUp(self):
        self.MAX_LOG_LINES = 100
        self.procdb = client.SQLClient(":memory:", self.MAX_LOG_LINES)
        self.s1 = helpers.build_stream(name="s1", path="/some/path/1")
        self.s2 = helpers.build_stream(name="s2", path="/some/path/2")
        self.s3 = helpers.build_stream(name="s3", path="/some/path/3")

        self.procdb.register_stream(self.s1)
        self.procdb.register_stream(self.s2)
        self.procdb.register_stream(self.s3)

        self.m1 = helpers.build_module(name="m1",
                                       destination_paths={
                                           "path1": "/some/path/1",
                                           "path2": "/some/path/2"})
        self.m2 = helpers.build_module(name="m2",
                                       destination_paths={
                                           "path3": "/some/path/3"},
                                       source_paths={
                                           "path1": "/some/path/1",
                                           "path2": "/some/path/2"})
        self.procdb.register_module(self.m1)
        self.procdb.register_module(self.m2)

    def test_clears_database(self):
        self.procdb.clear_db()
        self.assertEqual(self.procdb.find_all_modules(), [])
        self.assertEqual(self.procdb.find_all_streams(), [])

    def test_finds_streams(self):
        s1_r = self.procdb.find_stream_by_id(self.s1.id)
        self.assertEqual(self.s1, s1_r)

        s1_r = self.procdb.find_stream_by_name(self.s1.name)
        self.assertEqual(self.s1, s1_r)

        s3_r = self.procdb.find_stream_by_path(self.s3.path)
        self.assertEqual(self.s3, s3_r)

        m1_streams = self.procdb.find_streams_by_module(
            self.m1.id, "destination")
        helpers.assertUnorderedListEqual(self, [self.s2, self.s1], m1_streams)

        streams = self.procdb.find_all_streams()
        helpers.assertUnorderedListEqual(
            self, [self.s1, self.s2, self.s3], streams)

    def test_finds_modules(self):
        m2_r = self.procdb.find_module_by_id(self.m2.id)
        self.assertEqual(self.m2, m2_r)

        m1_r = self.procdb.find_module_by_id(self.m1.id)
        self.assertEqual(self.m1, m1_r)

        m2_r = self.procdb.find_module_by_name(self.m2.name)
        self.assertEqual(self.m2, m2_r)

        modules = self.procdb.find_all_modules()
        helpers.assertUnorderedListEqual(self, [self.m1, self.m2], modules)

    def test_logs_to_modules(self):
        logs = ["test_m%d_1", "test_m%d_2"]
        for line in logs:
            self.procdb.add_log_by_module(line % 1, self.m1.id)
            self.procdb.add_log_by_module(line % 2, self.m2.id)

        m1_logs = self.procdb.find_logs_by_module(self.m1.id)
        m2_logs = self.procdb.find_logs_by_module(self.m2.id)
        for i in range(len(logs)):
            self.assertRegex(m1_logs[i], logs[i] % 1)
            self.assertRegex(m2_logs[i], logs[i] % 2)

    def test_updates_modules(self):
        self.m1.pid = 10
        self.m1.status = module.STATUS_RUNNING
        self.procdb.update_module(self.m1)
        m1_r = self.procdb.find_module_by_name(self.m1.name)
        self.assertEqual(self.m1, m1_r)

    def test_keeps_maxlogs_log_entries(self):
        NUM_INSERTED_LINES = self.MAX_LOG_LINES*2
        for i in range(NUM_INSERTED_LINES):
            self.procdb.add_log_by_module("m1_%d" % i, self.m1.id)
            self.procdb.add_log_by_module("m2_%d" % i, self.m2.id)
        m1_logs = self.procdb.find_logs_by_module(self.m1.id)
        m2_logs = self.procdb.find_logs_by_module(self.m2.id)
        # only store MAX_LOGS
        self.assertEqual(len(m1_logs), self.MAX_LOG_LINES)
        self.assertEqual(len(m2_logs), self.MAX_LOG_LINES)
        # keeps most recent entries
        last_log = "m1_%d" % (NUM_INSERTED_LINES-self.MAX_LOG_LINES)
        self.assertRegex(m1_logs[0], last_log)
        last_log = "m2_%d" % (NUM_INSERTED_LINES-self.MAX_LOG_LINES)
        self.assertRegex(m2_logs[0], last_log)

