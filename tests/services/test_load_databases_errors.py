import unittest
import logging
import tempfile
import os

from joule.services import load_databases

logger = logging.getLogger('joule')


class TestLoadDatabasesErrors(unittest.TestCase):

    def test_nilmdb_requires_url(self):
        conf_str = """
                    [Main]
                    name=invalid_nilmdb
                    # capitalization doesn't matter
                    backend=NilmDB 
                    """
        with self.assertLogs(level="ERROR") as logs:
            attempt_load(conf_str)
        all_logs = ' '.join(logs.output).lower()
        self.assertTrue('url' in all_logs)

    def test_sqlite_requires_path(self):
        conf_str = """
                    [Main]
                    name=invalid_sqlite
                    backend=sqlite 
                    """
        with self.assertLogs(level="ERROR") as logs:
            attempt_load(conf_str)
        all_logs = ' '.join(logs.output).lower()
        self.assertTrue('path' in all_logs)

    def test_invalid_syntax(self):
        conf_str = """
                    name=invalid_syntax
                    """
        with self.assertLogs(level="ERROR") as logs:
            attempt_load(conf_str)
        all_logs = ' '.join(logs.output).lower()
        self.assertTrue('error' in all_logs)

    def test_must_have_main_section(self):
        conf_str = """
                    [Invalid]
                    name=invalid_syntax
                    """
        with self.assertLogs(level="ERROR") as logs:
            attempt_load(conf_str)
        all_logs = ' '.join(logs.output).lower()
        self.assertTrue('main' in all_logs)

    def test_must_have_name(self):
        conf_str = """
                    [Main]
                    backend=nilmdb
                    url=http://localhost/nilmdb
                    """
        with self.assertLogs(level="ERROR") as logs:
            attempt_load(conf_str)
        all_logs = ' '.join(logs.output).lower()
        self.assertTrue('name' in all_logs)

    def test_invalid_backend(self):
        conf_str = """
                    [Main]
                    name=Test
                    backend=unknown
                    """
        with self.assertLogs(level="ERROR") as logs:
            attempt_load(conf_str)
        all_logs = ' '.join(logs.output).lower()
        self.assertTrue('backend' in all_logs)


def attempt_load(conf_str):
    with tempfile.TemporaryDirectory() as conf_dir:
        with open(os.path.join(conf_dir, "invalid.conf"), 'w') as f:
            f.write(conf_str)
        load_databases.run(conf_dir)
