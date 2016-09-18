from joule.daemon.daemon import Daemon, DaemonError
import configparser
import tempfile
import unittest
import os
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
    @mock.patch("joule.daemon.daemon.procdb_client",autospec=True)
    def test_it_creates_modules(self,mock_procdb,mock_module):
        """creates a module for every *.conf file (ignores others"""
        module_names = ['module1.conf','ignored','temp.conf~','module2.conf']
        MODULE_COUNT = 2
        with tempfile.TemporaryDirectory() as dir:
            for name in module_names:
                #create a stub module configuration (needed for configparser)
                with open(os.path.join(dir,name),'w') as f:
                    f.write('[Main]\n')
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
