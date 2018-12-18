import unittest
import configparser
import tempfile
import testing.postgresql

from joule.services import load_config
from joule.models import config


class TestLoadConfigs(unittest.TestCase):

    def test_loads_default_config(self):
        my_config = load_config.run(verify=False)
        self.assertEqual(my_config.ip_address, config.DEFAULT_CONFIG['Main']['IPAddress'])

    def test_customizes_config(self):
        parser = configparser.ConfigParser()
        parser.read_string("""
            [Main]
            IPAddress = 8.8.8.8
            Database = new_db
            InsertPeriod = 20
        """)
        my_config = load_config.run(custom_values=parser, verify=False)
        self.assertEqual(my_config.ip_address, "8.8.8.8")
        self.assertEqual(my_config.insert_period, 20)

    def test_verifies_directories_exist(self):
        postgresql = testing.postgresql.Postgresql()
        db_url = postgresql.url()
        with tempfile.TemporaryDirectory() as module_dir:
            with tempfile.TemporaryDirectory() as stream_dir:
                parser = configparser.ConfigParser()
                parser.read_string("""
                            [Main]
                            ModuleDirectory=%s
                            StreamDirectory=%s
                            Database=%s
                        """ % (module_dir, stream_dir, db_url[13:]))
                my_config = load_config.run(custom_values=parser)
                self.assertEqual(my_config.stream_directory, stream_dir)
                self.assertEqual(my_config.module_directory, module_dir)
        postgresql.stop()
