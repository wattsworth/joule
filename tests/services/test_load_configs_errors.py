import unittest
import configparser
import tempfile
import asyncio

from joule.services import load_config
from joule.errors import ConfigurationError


class TestLoadConfigErrors(unittest.TestCase):

    def test_error_if_directories_do_not_exist(self):
        with tempfile.TemporaryDirectory() as good_dir1:
            with tempfile.TemporaryDirectory() as good_dir2:
                bad_dir = "/does/not/exist"
                bad_module_dir = (bad_dir, good_dir1, good_dir2)
                bad_stream_dir = (good_dir1, bad_dir, good_dir2)
                for setup in zip(bad_module_dir, bad_stream_dir):
                    parser = configparser.ConfigParser()
                    parser.read_string("""
                                [Main]
                                ModuleDirectory=%s
                                StreamDirectory=%s
                            """ % setup)
                    with self.assertRaises(ConfigurationError):
                        load_config.run(custom_values=parser)

    def test_error_if_missing_database_configuration(self):
        with tempfile.TemporaryDirectory() as module_dir:
            with tempfile.TemporaryDirectory() as stream_dir:
                with tempfile.TemporaryDirectory() as sock_dir:
                    parser = configparser.ConfigParser()
                    parser.read_string("""
                                [Main]
                                ModuleDirectory=%s
                                StreamDirectory=%s
                                SocketDirectory=%s
                            """ % (module_dir, stream_dir, sock_dir))
                    with self.assertRaisesRegex(ConfigurationError, "database"):
                        load_config.run(custom_values=parser)

    def test_error_on_bad_ip_address(self):
        parser = configparser.ConfigParser()
        bad_ips = ["8.8.x.8", "bad", "", "900.8.4.100"]
        for ip in bad_ips:
            parser.read_string("""
                [Main]
                IPAddress=%s
            """ % ip)
            with self.assertRaisesRegex(ConfigurationError, "IPAddress"):
                load_config.run(custom_values=parser, verify=False)

    def test_error_on_bad_port(self):
        parser = configparser.ConfigParser()
        bad_ports = ["-3", "99999", "abc", ""]
        for port in bad_ports:
            parser.read_string("""
                [Main]
                IpAddress=127.0.0.1
                Port=%s
            """ % port)
            with self.assertRaisesRegex(ConfigurationError, "Port"):
                load_config.run(custom_values=parser, verify=False)

    def test_errors_on_invalid_insert_period(self):
        bad_periods = ['-1', '0', 'abc', '']
        for period in bad_periods:
            parser = configparser.ConfigParser()
            parser.read_string("""
                        [Main]
                        InsertPeriod = %s
                        """ % period)
            with self.assertRaisesRegex(ConfigurationError, "InsertPeriod"):
                load_config.run(custom_values=parser, verify=False)

    def test_errors_on_invalid_cleanup_period(self):
        bad_periods = ['-1', '0', 'abc', '', '30']
        for period in bad_periods:
            parser = configparser.ConfigParser()
            parser.read_string("""
                        [Main]
                        InsertPeriod = 50
                        CleanupPeriod = %s
                        """ % period)
            with self.assertRaisesRegex(ConfigurationError, "CleanupPeriod"):
                load_config.run(custom_values=parser, verify=False)

    def test_errors_on_invalid_max_log_lines(self):
        parser = configparser.ConfigParser()
        for bad_val in [-1, 'abc']:
            parser.read_string("""
                                    [Main]
                                    MaxLogLines = %s
                                    """ % bad_val)
            with self.assertRaisesRegex(ConfigurationError, "MaxLogLines"):
                load_config.run(custom_values=parser, verify=False)

    def test_errors_if_nilmdb_not_available(self):
        with tempfile.TemporaryDirectory() as module_dir:
            with tempfile.TemporaryDirectory() as stream_dir:
                with tempfile.TemporaryDirectory() as sock_dir:
                    parser = configparser.ConfigParser()
                    parser.read_string("""
                                       [Main]
                                       ModuleDirectory=%s
                                       StreamDirectory=%s
                                       SocketDirectory=%s
                                       NilmdbUrl=http://127.0.0.1:234/bad_nilmdb
                                   """ % (module_dir, stream_dir, sock_dir))
                    with self.assertRaisesRegex(ConfigurationError, "NilmDB"):
                        load_config.run(custom_values=parser)
                        
