from joule.daemon import module
from . import helpers
import unittest

class TestModule(unittest.TestCase):
    def setUp(self):
        self.parser = module.Parser()
        self.my_module = module.Module(name="test",
                                       description="test_description",
                                       exec_cmd = "/path/to/exec --args",
                                       source_paths = { "path1":"/input/path1",
                                                        "path2":"/input/path2"},
                                       destination_paths = {"path1":"/output/path1",
                                                            "path2":"/output/path2"})
        self.base_config = helpers.parse_configs(
            """[Main]
                 name = test
                 description = test_description
                 exec_cmd = /path/to/exec --args
               [Source]
                 path1 = /input/path1
                 path2 = /input/path2
               [Destination]
                 path1 = /output/path1
                 path2 = /output/path2
            """)

    def test_parses_base_config(self):
        parsed_module = self.parser.run(self.base_config)
        self.assertEqual(parsed_module,self.my_module)

    def test_has_string_representation(self):
        self.assertRegex("%s"%self.my_module,self.my_module.name)
        self.my_module.name=""
        self.assertRegex("%s"%self.my_module,"unknown")
        
    def test_sorts_by_id(self):
        m1 = helpers.build_module(name='m1',id=1)
        m2 = helpers.build_module(name='m2',id=2)
        self.assertGreater(m2,m1)
        self.assertLess(m1,m2)


