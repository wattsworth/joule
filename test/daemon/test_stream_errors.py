from joule.daemon import stream
from joule.daemon.errors import ConfigError
from test import helpers
import unittest

class TestStreamErrors(unittest.TestCase):
    def setUp(self):
        self.parser = stream.Parser()
        self.base_config = helpers.parse_configs(
            """[Main]
                 name = test
                 description = test_description                 
                 path = /some/path/to/data
                 datatype = float32
                 keep = 1w
                 decimate = yes
               [Element1]
                 name = e1
            """)
    def test_errors_on_missing_info(self):
        self.base_config.remove_option("Main","name")
        with self.assertRaisesRegex(ConfigError,'name'):
            self.parser.run(self.base_config)

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
        
    def test_errors_on_missing_elements_sections(self):
        """Must have at least one element"""
        self.base_config.remove_section("Element1")
        with self.assertRaises(ConfigError):
            self.parser.run(self.base_config)

    def test_errors_on_duplicate_element_names(self):
        """each element must have a unique name"""
        self.base_config.add_section("Element2")
        self.base_config["Element2"]["name"] = "e1"
        with self.assertRaisesRegex(ConfigError,'unique'):
            self.parser.run(self.base_config)
        
    def evaluate_bad_values(self,setting_name,bad_settings,section="Main"):
        for setting in bad_settings:
            with self.subTest(setting=setting):
                self.base_config[section][setting_name]=setting
                with self.assertRaisesRegex(ConfigError,setting_name):
                    self.parser.run(self.base_config)

        
