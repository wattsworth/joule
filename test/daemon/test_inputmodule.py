from joule.daemon.inputmodule import InputModule
from joule.daemon.errors import DaemonError
import test.util as util
import unittest

class TestConfigFile(unittest.TestCase):
    def setUp(self):
        self.module = InputModule()
        self.base_config = util.parse_configs(
            """[Main]
                 name = module name
                 description = optional
               [Source]
                 exec = /path/to/exec --args
               [Destination]
                 path = /simple/demo
                 datatype = float32
                 keep = 1w
               [Stream1]
                 name = stream1
            """)
    def test_parses_base_config(self):
        us_in_week = 7*24*60*60*1e6
        self.module.initialize(self.base_config)
        self.assertEqual(us_in_week,self.module.destination.keep_us)
    def test_errors_on_missing_dest_section(self):
        self.base_config.remove_section("Destination")
        with self.assertRaises(DaemonError):
            self.module.initialize(self.base_config)
    def test_errors_on_missing_name(self):
        self.base_config.remove_section("Main")
        with self.assertRaises(DaemonError):
            self.module.initialize(self.base_config)        
    def test_errors_on_blank_name(self):
        self.base_config['Main']['name']=""
        with self.assertRaisesRegex(DaemonError,"name"):
            self.module.initialize(self.base_config)        
        
    def test_errors_on_missing_stream_sections(self):
        """Must have at least one stream"""
        self.base_config.remove_section("Stream1")
        with self.assertRaises(DaemonError):
            self.module.initialize(self.base_config)
    def evaluate_bad_values(self,setting_name,bad_settings):
        for setting in bad_settings:
            with self.subTest(setting=setting):
                self.base_config['Destination'][setting_name]=setting
                with self.assertRaisesRegex(DaemonError,setting_name):
                    self.module.initialize(self.base_config)
        
