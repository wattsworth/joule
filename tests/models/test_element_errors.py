import unittest

from joule.models import Element
from joule.models import element
from joule.errors import ConfigurationError
from tests import helpers


class TestElementErrors(unittest.TestCase):

    def setUp(self):
        config = helpers.parse_configs(
            """[Element1]
                 name = test
                 plottable = no
                 offset = 5.2
            """)
        self.base_config = config['Element1']

    def test_must_have_name(self):
        self.base_config['name'] = ""
        with self.assertRaisesRegex(ConfigurationError, "name"):
            element.from_config(self.base_config)

    def test_sensible_bounds(self):
        """default_min<default_max or both == 0 for autoscale"""
        self.base_config['default_min'] = '10'
        self.base_config['default_max'] = '-10'
        with self.assertRaisesRegex(ConfigurationError, "default_min"):
            element.from_config(self.base_config)

    def test_errors_on_bad_offsets(self):
        bad_offsets = ['a', '*', '0y']
        self.evaluate_bad_values("offset", bad_offsets)

    def test_errors_on_bad_scale_factor(self):
        bad_values = ['a', '*', '0y']
        self.evaluate_bad_values("scale_factor", bad_values)

    def test_errors_on_bad_default_min(self):
        bad_values = ['a', '*', '0y']
        self.evaluate_bad_values("default_min", bad_values)

    def test_errors_on_bad_default_max(self):
        bad_values = ['a', '*', '0y']
        self.evaluate_bad_values("default_max", bad_values)

    def test_errors_on_bad_bool(self):
        bad_values = ['asdf', 'not_valid']
        self.evaluate_bad_values("plottable", bad_values)

    def test_errors_on_bad_display_type(self):
        bad_values = ['lollipops', '', 'circles']
        self.evaluate_bad_values("display_type", bad_values)

    def evaluate_bad_values(self, setting_name, bad_settings):
        for setting in bad_settings:
            with self.subTest(setting=setting):
                self.base_config[setting_name] = setting
                with self.assertRaisesRegex(ConfigurationError, setting_name):
                    element.from_config(self.base_config)

    def test_errors_on_invalid_update(self):
        # value types must be correct
        e = Element(name="test")
        with self.assertRaises(ConfigurationError):
            e.update_attributes({
                "name": "new name",
                "default_min": 'invalid',
            })
        with self.assertRaises(ConfigurationError):
            e.update_attributes({
                "name": "new name",
                "offset": '',
            })
        # default_min < default_max
        with self.assertRaises(ConfigurationError) as error:
            e.update_attributes({
                "name": "new name",
                "default_min": 100,
                "default_max": 10
            })
        self.assertTrue('default_min' in str(error.exception))