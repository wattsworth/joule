import unittest
from joule.procdb import client
from unittest import mock
from . import helpers


class TestClient(unittest.TestCase):

    def setUp(self):
        self.procdb = client.SQLClient(":memory:")

    def tearDown(self):
        pass

    def test_returns_none_if_module_not_found(self):
        m = self.procdb.find_module_by_id(2)
        self.assertIsNone(m)
        m = self.procdb.find_all_modules()
        self.assertEqual(m, [])

    def test_returns_none_if_stream_not_found(self):
        s = self.procdb.find_stream_by_id(2)
        self.assertIsNone(s)

    def test_warns_on_missing_streams(self):
        m = helpers.build_module(
            destination_paths={"path1": "/does/not/exist"})
        with self.assertLogs(level='ERROR'):
            self.procdb.register_module(m)

    def test_detect_corrupt_streams_modules_table(self):
        pass

    def test_raises_error_with_bad_direction_parameter(self):
        with self.assertRaisesRegex(client.ProcDbError, "direction"):
            self.procdb.find_streams_by_module(mock.Mock(), "bad-parameter")
