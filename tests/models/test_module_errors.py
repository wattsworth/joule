import unittest
from joule.errors import ConfigurationError
from joule.models import module  # for helper functions
from tests import helpers


class TestModuleErrors(unittest.TestCase):

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
            module.from_config(self.base_config)

    def test_errors_on_bad_name(self):
        self.base_config.remove_option('Main', 'name')
        with self.assertRaisesRegex(ConfigurationError, 'name'):
            module.from_config(self.base_config)
        self.base_config.set('Main', 'name', '')
        with self.assertRaisesRegex(ConfigurationError, 'name'):
            module.from_config(self.base_config)

