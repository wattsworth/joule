from joule.daemon.inputmodule import InputModule
from joule.daemon.errors import DaemonError
import configparser
import unittest

class TestConfigFile(unittest.TestCase):
    def setUp(self):
        self.module = InputModule()
        self.base_config = self.parse_configs(
            """[Destination]
                 path = /simple/demo
                 datatype = float32
                 keep = 1w
               [Stream]
            """)
    def test_parses_base_config(self):
        us_in_week = 7*24*60*60*1e6
        self.module.initialize(self.base_config)
        self.assertEqual(us_in_week,self.module.destination.keep_us)
    def test_errors_on_missing_dest_section(self):
        self.base_config.remove_section("Destination")
        with self.assertRaises(DaemonError):
            self.module.initialize(self.base_config)
    def test_errors_on_bad_path(self):
        """path must be of form /dir/subdir/../file"""
        bad_paths=["","bad name","/tooshort","/*bad&symb()ls"]
        self.evaluate_bad_values("path",bad_paths)
    def test_errors_on_bad_keep(self):
        """keep is # and timeunit (eg 1w, 30h, 2y) or False"""
        bad_keeps=["0w","3","w","something random","-2h"]
        self.evaluate_bad_values("keep",bad_keeps)
    def test_errors_on_bad_datatype(self):
        bad_datatypes=["","intz","0"]
        self.evaluate_bad_values("datatype",bad_datatypes)
    @unittest.skip("TODO")
    def test_allows_no_keep(self):
        pass
    
    def parse_configs(self,config_str):
        config = configparser.ConfigParser()
        config.read_string(config_str)
        return config
    def evaluate_bad_values(self,setting_name,bad_settings):
        for setting in bad_settings:
            with self.subTest(setting=setting):
                self.base_config['Destination'][setting_name]=setting
                with self.assertRaisesRegex(DaemonError,setting_name):
                    self.module.initialize(self.base_config)
        
