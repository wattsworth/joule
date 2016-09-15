import joule.daemon.stream as stream
from joule.daemon.errors import DaemonError
import test.util as util
import unittest

class TestStreamParsing(unittest.TestCase):
    def setUp(self):
        self.parser = stream.Parser()
        config = util.parse_configs(
            """[Stream1]
                 name = test
                 plottable = no
                 offset = 5.2
            """)
        self.base_config = config['Stream1']
    def test_parses_base_config(self):
        stream = self.parser.run(self.base_config)
        self.assertEqual(stream.name,"test")
        self.assertEqual(stream.plottable,False)
        self.assertEqual(stream.discrete,False) #default value
        self.assertEqual(stream.offset,5.2)
        self.assertEqual(stream.scale_factor,1.0) #default value
        
    def test_must_have_name(self):
        self.base_config['name'] = ""
        with self.assertRaisesRegex(DaemonError,"name"):
            self.parser.run(self.base_config)

    def test_sensible_bounds(self):
        """default_min<default_max or both == 0 for autoscale"""
        self.base_config['default_min']='10'
        self.base_config['default_max']='-10'
        with self.assertRaisesRegex(DaemonError,"default_min"):
            self.parser.run(self.base_config)

    def test_errors_on_bad_offsets(self):
        bad_offsets=['a','*','0y']
        self.evaluate_bad_values("offset",bad_offsets)
    def test_errors_on_bad_scale_factor(self):
        bad_values=['a','*','0y']
        self.evaluate_bad_values("scale_factor",bad_values)
    def test_errors_on_bad_default_min(self):
        bad_values=['a','*','0y']
        self.evaluate_bad_values("default_min",bad_values)
    def test_errors_on_bad_default_max(self):
        bad_values=['a','*','0y']
        self.evaluate_bad_values("default_max",bad_values)
        
    
    def evaluate_bad_values(self,setting_name,bad_settings):
        for setting in bad_settings:
            with self.subTest(setting=setting):
                self.base_config[setting_name]=setting
                with self.assertRaisesRegex(DaemonError,setting_name):
                    self.parser.run(self.base_config)

