from joule.daemon.daemon import Daemon, DaemonError
import configparser
import tempfile
import unittest
from unittest import mock

class TestConfigFile(unittest.TestCase):
    def setUp(self):
        self.daemon = Daemon()
        
    def test_errors_on_missing_sections(self):
        config = self.parse_configs(""" 
        [MissingMainSection]
        """)
        with self.assertRaises(DaemonError):
            self.daemon.initialize(config)
        
    def test_it_errors_out_if_bad_configs(self):
        config = self.parse_configs("""
        [Main]
        InputModuleDir=garbage
        """)
        with self.assertRaises(DaemonError):
            self.daemon.initialize(config)

    @mock.patch("joule.daemon.daemon.InputModule",autospec=True)
    def test_it_creates_modules(self,mock_module):
        """creates a module for every config file"""
        MODULE_COUNT = 4
        with tempfile.TemporaryDirectory() as dir:
            for i in range(MODULE_COUNT):
                #create a stub module configuration (needed for configparser)
                with tempfile.NamedTemporaryFile(dir=dir,delete=False) as f:
                    f.write(b'[Main]\n')
            config = self.parse_configs("""
            [Main]
            """)
            config["Main"]["InputModuleDir"]= dir
            self.daemon.initialize(config)
            self.assertEqual(MODULE_COUNT,len(self.daemon.input_modules))
    def parse_configs(self,config_str):
        config = configparser.ConfigParser()
        config.read_string(config_str)
        return config
