import unittest
import datetime
from joule.models import (DataStream, Element, data_stream)
from joule.errors import ConfigurationError
from tests import helpers


class TestStream(unittest.TestCase):
    def setUp(self):
        us_in_week = int(7 * 24 * 60 * 60 * 1e6)
        self.my_stream = data_stream.DataStream(name="test",
                                                description="test_description",
                                                datatype=DataStream.DATATYPE.FLOAT32,
                                                keep_us=us_in_week,
                                                decimate=True,
                                                updated_at=datetime.datetime.now())
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
        my_stream = DataStream(name='test', description='a test',
                               datatype=DataStream.DATATYPE.FLOAT32, keep_us=DataStream.KEEP_ALL,
                               updated_at=datetime.datetime.now())
        self.assertIsNotNone(my_stream)
        # has a meaningful string representation
        self.assertTrue("test" in "%r" % my_stream)
        # if remote is not set, the pseudo attributes are empty
        self.assertEqual(my_stream.remote_node, '')
        self.assertEqual(my_stream.remote_path, '')
        # if remote is set, these attributes have values
        my_stream.set_remote("remote_url", "remote_path")
        self.assertEqual(my_stream.remote_node, "remote_url")
        self.assertEqual(my_stream.remote_path, "remote_path")

    def test_json(self):
        my_stream = DataStream(id=0, name='test', decimate=True,
                               datatype=DataStream.DATATYPE.UINT16,
                               updated_at=datetime.datetime.now())
        for j in range(4):
            my_stream.elements.append(Element(name="e%d" % j, index=j,
                                              display_type=Element.DISPLAYTYPE.CONTINUOUS))
        # turns streams into json
        json = my_stream.to_json()
        self.assertEqual(json['decimate'], True)
        self.assertEqual(json['name'], 'test')
        self.assertEqual(len(json['elements']), 4)
        # builds streams from json
        new_stream = data_stream.from_json(json)
        self.assertEqual(new_stream.id, my_stream.id)
        self.assertEqual(len(new_stream.elements), len(my_stream.elements))

    def test_parses_config(self):
        s = data_stream.from_config(self.base_config)
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
        s = data_stream.from_config(config)
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
        s = data_stream.from_config(config)
        self.assertEqual(s.keep_us, 100 * 60 * 60 * 1e6)

    def test_allows_no_description(self):
        self.base_config.remove_option("Main", "description")
        parsed_stream = data_stream.from_config(self.base_config)
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

    def test_from_nilmdb_metadata(self):
        metadata = {"name": "sinefit", "name_abbrev": "", "delete_locked": False,
                    "streams": [{"column": 0, "name": "stream_0",
                                 "units": None, "scale_factor": 1.0,
                                 "offset": 0.0, "plottable": False,
                                 "discrete": None, "default_min": -10,
                                 "default_max": None},
                                {"column": 1, "name": "stream_1",
                                 "units": None, "scale_factor": 2.0,
                                 "offset": 3.0, "plottable": True,
                                 "discrete": None, "default_min": None,
                                 "default_max": None},
                                {"column": 2, "name": "stream_2",
                                 "units": None, "scale_factor": 1.0,
                                 "offset": 10.5, "plottable": True,
                                 "discrete": None, "default_min": None,
                                 "default_max": None}]}
        my_stream = data_stream.from_nilmdb_metadata(metadata, "float32_3")
        # make sure the stream is created correctly
        self.assertEqual(my_stream.name, "sinefit")
        self.assertEqual(my_stream.layout, "float32_3")
        self.assertEqual(len(my_stream.elements), 3)
        my_stream.elements.sort(key=lambda e: e.index)
        elem0 = my_stream.elements[0]
        self.assertEqual(elem0.index, 0)
        self.assertEqual(elem0.name, 'stream_0')
        self.assertEqual(elem0.plottable, False)
        self.assertEqual(elem0.default_min, -10)
        self.assertEqual(elem0.default_max, None)
        elem2 = my_stream.elements[2]
        self.assertEqual(elem2.index, 2)
        self.assertEqual(elem2.name, 'stream_2')
        self.assertEqual(elem2.plottable, True)
        self.assertEqual(elem2.scale_factor, 1.0)
        self.assertEqual(elem2.offset, 10.5)

    def test_from_nilmdb_no_metadata(self):
        my_stream = data_stream.from_nilmdb_metadata({'name': 'test'}, "float32_3")
        # make sure the stream is created correctly
        self.assertEqual(my_stream.name, "test")
        self.assertEqual(my_stream.layout, "float32_3")
        self.assertEqual(len(my_stream.elements), 3)
        my_stream.elements.sort(key=lambda e: e.index)
        elem0 = my_stream.elements[0]
        self.assertEqual(elem0.index, 0)
        self.assertEqual(elem0.name, 'Element1')
        self.assertEqual(elem0.plottable, True)
        self.assertEqual(elem0.default_min, None)
        self.assertEqual(elem0.default_max, None)
        elem2 = my_stream.elements[2]
        self.assertEqual(elem2.index, 2)
        self.assertEqual(elem2.name, 'Element3')
        self.assertEqual(elem2.plottable, True)
        self.assertEqual(elem2.scale_factor, 1.0)
        self.assertEqual(elem2.offset, 0.0)

    def test_to_nilmdb_metadata(self):
        my_stream = DataStream(name="test", datatype=DataStream.DATATYPE.INT16,
                               updated_at=datetime.datetime.now())
        my_stream.elements.append(
            Element(name="e0", index=0, plottable=True, offset=0.0, default_min=-5, scale_factor=1.0))
        my_stream.elements.append(
            Element(name="e1", index=1, plottable=True, units="watts", offset=3.5, scale_factor=1.0))
        metadata = my_stream.to_nilmdb_metadata()
        # NOTE: The plottable flag is always True (see TODO in element.py)
        expected = {"name": "test", "name_abbrev": "", "delete_locked": False,
                    "streams": [{"column": 0, "name": "e0",
                                 "units": None, "scale_factor": 1.0,
                                 "offset": 0.0, "plottable": True,
                                 "discrete": False, "default_min": -5,
                                 "default_max": None},
                                {"column": 1, "name": "e1",
                                 "units": "watts", "scale_factor": 1.0,
                                 "offset": 3.5, "plottable": True,
                                 "discrete": False, "default_min": None,
                                 "default_max": None}]}
        self.assertEqual(expected, metadata)
