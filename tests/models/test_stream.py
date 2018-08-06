import unittest

from joule.models import (Stream, Element, ConfigurationError, stream)
from tests import helpers


class TestStream(unittest.TestCase):
    def setUp(self):
        us_in_week = int(7 * 24 * 60 * 60 * 1e6)
        self.my_stream = stream.Stream(name="test",
                                       description="test_description",
                                       datatype=Stream.DATATYPE.FLOAT32,
                                       keep_us=us_in_week,
                                       decimate=True)
        self.my_stream.elements.append(Element(name="e1", index=0,
                                               display_type=Element.DISPLAYTYPE.CONTINUOUS))
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

    def test_attributes(self):
        my_stream = Stream(name='test', description='a test',
                           datatype=Stream.DATATYPE.FLOAT32, keep_us=Stream.KEEP_ALL)
        self.assertIsNotNone(my_stream)
        # has a meaningful string representation
        self.assertTrue("test" in "%r" % my_stream)

    def test_json(self):
        my_stream = Stream(id=0, name='test', decimate=True, datatype=Stream.DATATYPE.UINT16)
        for j in range(4):
            my_stream.elements.append(Element(name="e%d" % j, index=j,
                                              display_type=Element.DISPLAYTYPE.CONTINUOUS))
        # turns streams into json
        json = my_stream.to_json()
        self.assertEqual(json['decimate'], True)
        self.assertEqual(json['name'], 'test')
        self.assertEqual(len(json['elements']), 4)
        # builds streams from json
        new_stream = stream.from_json(json)
        self.assertEqual(new_stream.id, my_stream.id)
        self.assertEqual(len(new_stream.elements), len(my_stream.elements))

    def test_parses_config(self):
        s = stream.from_config(self.base_config)
        self.assertEqual(s.name, self.base_config["Main"]["name"])

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
        s = stream.from_config(config)
        self.assertEqual(s.keep_us, 0)

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
        s = stream.from_config(config)
        self.assertEqual(s.keep_us, 100 * 60 * 60 * 1e6)

    def test_allows_no_description(self):
        self.base_config.remove_option("Main", "description")
        parsed_stream = stream.from_config(self.base_config)
        self.assertEqual(parsed_stream.description, "")

    def test_computes_layout(self):
        """data_format returns float32_4 for example"""
        self.my_stream.elements = []
        for i in range(4):
            self.my_stream.elements.append(Element(name="%d" % i))
        self.assertEqual(self.my_stream.layout, "float32_4")
        self.assertEqual(self.my_stream.data_width, 5)

    def test_has_string_representation(self):
        self.assertRegex("%s" % self.my_stream, self.my_stream.name)

    def test_updates(self):
        self.my_stream.update_attributes({
            "name": "new name",
            "description": "new description",
            "elements": [
                {"name": "new name"},
            ]
        })
        self.assertEqual("new name", self.my_stream.name)
        self.assertEqual("new description", self.my_stream.description)
        # updates element attributes
        self.assertEqual("new name", self.my_stream.elements[0].name)

        # number of elements in the request must match the elements in the stream
        with self.assertRaises(ConfigurationError):
            self.my_stream.update_attributes({
                "name": "new name",
                "description": "new description",
                "elements": [
                    {"name": "new name"},
                    {"extra", "causes error"}
                ]
            })
