from typing import Dict
import unittest
import logging
import tempfile
import os
from joule.models import (DatabaseConfig)
from joule.services import load_databases

logger = logging.getLogger('joule')


class TestLoadDatabases(unittest.TestCase):

    def test_parses_configs(self):

        configs = [
            # nilmdb database
            """
            [Main] 
              name = db1
              url = http://localhost/nilmdb
              backend=nilmdb
            """,
            # timescale database
            """
            [Main] 
              name = db2
              url = 127.0.0.1:5432
              backend=timescale
              username=admin
              password=secret
            """,
            # sqlite database
            """
            [Main] 
              name = db3
              path = /tmp/sql.db
              backend=sqlite
            """
        ]
        databases: Dict[str, DatabaseConfig] = {}
        with tempfile.TemporaryDirectory() as conf_dir:
            # write the configs in 0.conf, 1.conf, ...
            i = 0
            for conf in configs:
                with open(os.path.join(conf_dir, "%d.conf" % i), 'w') as f:
                    f.write(conf)
                i += 1
                databases = load_databases.run(conf_dir)
        self.assertEqual(len(databases), 3)
        self.assertEqual(databases['db1'].url, "http://localhost/nilmdb")
        self.assertEqual(databases['db2'].engine_config,
                         "postgresql://admin:secret@127.0.0.1:5432")
        self.assertEqual(databases['db3'].engine_config,
                         "sqlite:////tmp/sql.db")
