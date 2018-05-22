import unittest

from joule.models import (ConfigurationError)
from joule.models import stream   # for helper functions
from tests import helpers


class TestStreamErrors(unittest.TestCase):

    def setUp(self):
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
        self.base_config.remove_option("Main", "name")
        with self.assertRaisesRegex(ConfigurationError, 'name'):
            stream.from_config(self.base_config)

    def test_errors_on_bad_path(self):
        """path must be of form /dir/subdir/../file"""
        bad_paths = ["", "bad name", "/tooshort", "/*bad&symb()ls"]
        self.evaluate_bad_values("path", bad_paths)
        # but allows paths with _ and -
        good_paths = ["/meters-4/prep-a", "/meter_4/prep-b", "/path  with/ spaces"]
        self.evaluate_good_values("path", good_paths)
        
    def test_errors_on_bad_keep(self):
        """keep is # and timeunit (eg 1w, 30h, 2y) or False"""
        bad_keeps = ["0w", "3", "w", "something random", "-2h"]
        self.evaluate_bad_values("keep", bad_keeps)

    def test_errors_on_bad_datatype(self):
        bad_datatypes = ["", "intz", "0"]
        self.evaluate_bad_values("datatype", bad_datatypes)

    def test_errors_on_missing_elements_sections(self):
        """Must have at least one element"""
        self.base_config.remove_section("Element1")
        with self.assertRaises(ConfigurationError):
            stream.from_config(self.base_config)

    def evaluate_bad_values(self, setting_name, bad_settings, section="Main"):
        for setting in bad_settings:
            with self.subTest(setting=setting):
                self.base_config[section][setting_name] = setting
                with self.assertRaisesRegex(ConfigurationError, setting_name):
                    stream.from_config(self.base_config)

    def evaluate_good_values(self, setting_name, settings, section="Main"):
        for setting in settings:
            with self.subTest(setting=setting):
                self.base_config[section][setting_name] = setting
                stream.from_config(self.base_config)

