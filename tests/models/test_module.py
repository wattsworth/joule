from joule.models import module, ConfigurationError

from tests import helpers
import unittest


class TestModule(unittest.TestCase):

    def setUp(self):
        self.config = helpers.parse_configs(
            """[Main]
                 name = test
                 description = long text
                 exec_cmd = /bin/runit.sh
                 has_interface = yes
               [Arguments]
                 arg1 = val1
                 arg2 = val2
            """)

# Test module parsing (from_config)

    def test_parses_base_config(self):
        m = module.from_config(self.config)
        self.assertEqual(m.name, "test")
        self.assertEqual(m.description, "long text")
        self.assertEqual(m.exec_cmd, "/bin/runit.sh")
        self.assertEqual(m.has_interface, True)
        self.assertEqual(len(m.arguments), 2)  # default value
        self.assertEqual(m.arguments["arg1"], "val1")
        self.assertEqual(m.arguments["arg2"], "val2")

    def test_uses_default_values(self):
        self.config.remove_section("Arguments")
        self.config.remove_option("Main", "has_interface")
        self.config.remove_option("Main", "description")
        m = module.from_config(self.config)
        self.assertEqual(m.description, "")
        self.assertEqual(m.has_interface, False)
        self.assertEqual(len(m.arguments), 0)

    def test_requires_name_setting(self):
        self.config.remove_option("Main", "name")
        with self.assertRaisesRegex(ConfigurationError, "name"):
            module.from_config(self.config)
