from joule.models import module, DataStream, Element
from joule.errors import ConfigurationError
from tests import helpers
import unittest


class TestModule(unittest.TestCase):

    def setUp(self):
        self.config = helpers.parse_configs(
            """[Main]
                 name = test
                 description = long text
                 exec_cmd = /bin/runit.sh
                 is_app = yes
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
        self.assertEqual(m.is_app, True)
        self.assertEqual(len(m.arguments), 2)  # default value
        self.assertEqual(m.arguments["arg1"], "val1")
        self.assertEqual(m.arguments["arg2"], "val2")

    def test_uses_default_values(self):
        self.config.remove_section("Arguments")
        self.config.remove_option("Main", "is_app")
        self.config.remove_option("Main", "description")
        m = module.from_config(self.config)
        self.assertEqual(m.description, "")
        self.assertEqual(m.is_app, False)
        self.assertEqual(len(m.arguments), 0)

    def test_requires_name_setting(self):
        self.config.remove_option("Main", "name")
        with self.assertRaisesRegex(ConfigurationError, "name"):
            module.from_config(self.config)

    def test_has_json_representation(self):
        # create an input stream
        src = DataStream(id=0, name="source", keep_us=100, datatype=DataStream.DATATYPE.FLOAT32)
        src.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in range(3)]
        # create an output stream
        dest = DataStream(id=1, name="dest", keep_us=100, datatype=DataStream.DATATYPE.UINT16)
        dest.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.EVENT) for x in range(5)]
        m = module.from_config(self.config)
        m.inputs = {'input': src}
        m.outputs = dict(output=dest)
        result = m.to_json()
        # make sure basic attributes are in the output
        self.assertEqual(result['name'],'test')
        self.assertEqual(result['exec_cmd'],'/bin/runit.sh')
        # make sure inputs are included (name: id)
        self.assertEqual(result['inputs']['input'],0)
        self.assertEqual(result['outputs']['output'],1)
