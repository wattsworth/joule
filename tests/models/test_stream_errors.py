import unittest
from unittest import mock
from joule.errors import ConfigurationError
from joule.models import data_stream  # for helper functions
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

    def test_errors_on_missing_main(self):
        self.base_config.remove_section("Main")
        with self.assertRaisesRegex(ConfigurationError, 'Main'):
            data_stream.from_config(self.base_config)

    def test_errors_on_bad_name(self):
        bad_names = ["", "has/slash", "/other"]
        self.evaluate_bad_values("name", bad_names)

    def test_errors_on_missing_info(self):
        self.base_config.remove_option("Main", "name")
        with self.assertRaisesRegex(ConfigurationError, 'name'):
            data_stream.from_config(self.base_config)

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
            data_stream.from_config(self.base_config)

    @mock.patch('joule.models.element.from_config')
    def test_errors_on_invalid_elements(self, from_config: mock.Mock):
        from_config.side_effect = ConfigurationError()
        with self.assertRaisesRegex(ConfigurationError, 'element'):
            data_stream.from_config(self.base_config)

    def evaluate_bad_values(self, setting_name, bad_settings, section="Main"):
        for setting in bad_settings:
            with self.subTest(setting=setting):
                self.base_config[section][setting_name] = setting
                with self.assertRaisesRegex(ConfigurationError, setting_name):
                    data_stream.from_config(self.base_config)

    def evaluate_good_values(self, setting_name, settings, section="Main"):
        for setting in settings:
            with self.subTest(setting=setting):
                self.base_config[section][setting_name] = setting
                data_stream.from_config(self.base_config)
