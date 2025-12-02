import unittest
import configparser
import tempfile
import yarl
import testing.postgresql
import os

from joule.services import load_config
from joule.models import config


class TestLoadConfigs(unittest.TestCase):

    def test_loads_default_config(self):
        my_config = load_config.run(verify=False)
        self.assertEqual(my_config.socket_directory, config.DEFAULT_CONFIG['Main']['SocketDirectory'])
        self.assertFalse(my_config.echo_module_logs)

    def test_customizes_config(self):
        parser = configparser.ConfigParser()
        parser.read_string("""
            [Main]
            IPAddress = 8.8.8.8
            Port = 8080
            Database = new_db
            InsertPeriod = 20
            EchoModuleLogs = yes
        """)
        my_config = load_config.run(custom_values=parser, verify=False)
        self.assertEqual(my_config.ip_address, "8.8.8.8")
        self.assertEqual(my_config.insert_period, 20)
        self.assertTrue(my_config.echo_module_logs)

    def test_verifies_directories_exist(self):
        postgresql = testing.postgresql.Postgresql()
        db_url = postgresql.url()
        with(tempfile.TemporaryDirectory() as module_dir,
             tempfile.TemporaryDirectory() as stream_dir,
             tempfile.TemporaryDirectory() as socket_dir,
             tempfile.TemporaryDirectory() as event_dir,
             tempfile.TemporaryDirectory() as importer_dir,
             tempfile.TemporaryDirectory() as exporter_dir,
             tempfile.TemporaryDirectory() as data_dir):

            parser = configparser.ConfigParser()
            parser.read_string(f"""
                        [Main]
                        ModuleDirectory={module_dir}
                        DataStreamDirectory={stream_dir}
                        SocketDirectory={socket_dir}
                        EventStreamDirectory={event_dir}
                        ImporterConfigsDirectory={importer_dir}
                        ExporterConfigsDirectory={exporter_dir}
                        ImporterDataDirectory={data_dir+"/importer"}
                        ExporterDataDirectory={data_dir+"/exporter"}
                        Database={db_url[13:]}
                    """)
            my_config = load_config.run(custom_values=parser)
            self.assertEqual(my_config.stream_directory, stream_dir)
            self.assertEqual(my_config.module_directory, module_dir)
            # creates importer and exporter data directories
            self.assertTrue(os.path.isdir(data_dir+"/importer"))
            self.assertTrue(os.path.isdir(data_dir+"/exporter"))
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
