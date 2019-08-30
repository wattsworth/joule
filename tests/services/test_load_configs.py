import unittest
import configparser
import tempfile
import yarl
import testing.postgresql

from joule.services import load_config
from joule.models import config


class TestLoadConfigs(unittest.TestCase):

    def test_loads_default_config(self):
        my_config = load_config.run(verify=False)
        self.assertEqual(my_config.socket_directory, config.DEFAULT_CONFIG['Main']['SocketDirectory'])

    def test_customizes_config(self):
        parser = configparser.ConfigParser()
        parser.read_string("""
            [Main]
            IPAddress = 8.8.8.8
            Port = 8080
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
                with tempfile.TemporaryDirectory() as socket_dir:

                    parser = configparser.ConfigParser()
                    parser.read_string("""
                                [Main]
                                ModuleDirectory=%s
                                StreamDirectory=%s
                                SocketDirectory=%s
                                Database=%s
                            """ % (module_dir, stream_dir, socket_dir, db_url[13:]))
                    my_config = load_config.run(custom_values=parser)
                    self.assertEqual(my_config.stream_directory, stream_dir)
                    self.assertEqual(my_config.module_directory, module_dir)
        postgresql.stop()

    def test_loads_proxies(self):
        parser = configparser.ConfigParser()
        parser.read_string("""
                    [Proxies]
                    site1=http://localhost:5000
                    site two=https://othersite.com
                """)
        my_config = load_config.run(custom_values=parser, verify=False)
        self.assertEqual(my_config.proxies[0].url, yarl.URL("http://localhost:5000"))
        self.assertEqual(my_config.proxies[0].uuid, 0)
        self.assertEqual(my_config.proxies[0].name, "site1")

        self.assertEqual(my_config.proxies[1].url, yarl.URL("https://othersite.com"))
        self.assertEqual(my_config.proxies[1].uuid, 1)
        self.assertEqual(my_config.proxies[1].name, "site two")
