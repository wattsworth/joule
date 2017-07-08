from joule.daemon import stream, element
from test import helpers
import unittest


class TestStream(unittest.TestCase):

    def setUp(self):
        us_in_week = 7 * 24 * 60 * 60 * 1e6
        self.parser = stream.Parser()
        self.my_stream = stream.Stream(name="test",
                                       description="test_description",
                                       path="/some/path/to/data",
                                       datatype="float32",
                                       keep_us=us_in_week,
                                       decimate=True)
        self.my_stream.add_element(element.build_element("e1"))
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

    def test_parses_base_config(self):
        parsed_stream = self.parser.run(self.base_config)
        self.assertEqual(parsed_stream, self.my_stream)

    def test_allows_no_keep(self):
        config = helpers.parse_configs(
            """[Main]
                 name = test
                 description = test_description                 
                 path = /simple/demo
                 datatype = float32
                 keep = None
               [Element1]
                 name=1
            """)
        stream = self.parser.run(config)
        self.assertEqual(stream.keep_us, 0)

    def test_allows_long_keeps(self):
        config = helpers.parse_configs(
            """[Main]
                 name = test
                 description = test_description                 
                 path = /simple/demo
                 datatype = float32
                 keep = 100h
               [Element1]
                 name=1
            """)
        stream = self.parser.run(config)
        self.assertEqual(stream.keep_us, 100*60*60*1e6)
        
    def test_allows_no_description(self):
        self.base_config.remove_option("Main", "description")
        parsed_stream = self.parser.run(self.base_config)
        self.assertEqual(parsed_stream.description, "")

    def test_computes_layout(self):
        """data_format returns float32_4 for example"""
        self.my_stream.elements = []
        for i in range(4):
            self.my_stream.add_element(element.build_element(name="%d" % i))
        self.assertEqual(self.my_stream.layout, "float32_4")
        self.assertEqual(self.my_stream.data_width, 5)

    def test_has_string_representation(self):
        self.assertRegex("%s" % self.my_stream, self.my_stream.name)

    def test_sorts_by_id(self):
        s1 = helpers.build_stream(name='s1', id=1)
        s2 = helpers.build_stream(name='s2', id=2)
        self.assertGreater(s2, s1)
        self.assertLess(s1, s2)
