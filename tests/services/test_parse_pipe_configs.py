from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import unittest
from joule.models import (Base, Stream, Folder,
                          Element, ConfigurationError)
from joule.services import parse_pipe_config


class TestParsePipeConfig(unittest.TestCase):

    def setUp(self):
        # create a database
        engine = create_engine('sqlite://')
        Base.metadata.create_all(engine)
        self.db = Session(bind=engine)

        # /test/stream1:float32[e0,e1,e2]
        folder_test = Folder(name="test")
        stream1 = Stream(name="stream1", keep_us=100,
                         datatype=Stream.DATATYPE.FLOAT32)
        stream1.elements = [Element(name="e%d" % x, index=x, default_min=1) for x in range(3)]
        folder_test.streams.append(stream1)

        # /test/deeper/stream2:int8[e0,e1]
        folder_deeper = Folder(name="deeper")
        stream2 = Stream(name="stream2", datatype=Stream.DATATYPE.INT8)
        stream2.elements = [Element(name="e%d" % x, index=x) for x in range(2)]
        folder_deeper.streams.append(stream2)
        folder_deeper.parent = folder_test

        root = Folder(name="root")
        root.children = [folder_test]
        self.db.add(root)

    def test_parses_new_stream_configs(self):
        my_stream = parse_pipe_config.run("/test/new_stream:int8[x,y]", self.db)
        # ensure stream entered the database
        self.assertEqual(my_stream, self.db.query(Stream).filter_by(name="new_stream").one())
        # check stream datatype
        self.assertEqual(my_stream.datatype, Stream.DATATYPE.INT8)
        # check elements
        self.assertEqual(len(my_stream.elements), 2)
        for elem in my_stream.elements:
            self.assertTrue(elem.name in ['x', 'y'])
        # check parent folder
        self.assertEqual(my_stream.folder.name, "test")

    def test_parses_existing_stream_configs(self):
        existing_stream = self.db.query(Stream).filter_by(name="stream2").one()
        my_stream = parse_pipe_config.run("/test/deeper/stream2:int8[e0,e1]", self.db)
        # retrieved the existsing stream from the database
        self.assertEqual(my_stream, existing_stream)

    def test_parses_links_to_existing_configs(self):
        existing_stream = self.db.query(Stream).filter_by(name="stream2").one()
        my_stream = parse_pipe_config.run("/test/deeper/stream2", self.db)
        # retrieved the existsing stream from the database
        self.assertEqual(my_stream, existing_stream)

    def test_errors_on_invalid_configs(self):
        bad_configs = ["no/leading/slash", "/", "/invalid/datatype:uknown[x,y]",
                       "/bad/syntax:int[", "/bad/syntax:missing"]
        for config in bad_configs:
            with self.assertRaisesRegex(ConfigurationError, "invalid"):
                parse_pipe_config.run(config, self.db)

    def test_errors_on_stream_datatype_conflict(self):
        with self.assertRaisesRegex(ConfigurationError, "exists"):
            parse_pipe_config.run("/test/deeper/stream2:uint8[e0,e1]", self.db)

    def test_errors_on_stream_element_name_conflict(self):
        with self.assertRaisesRegex(ConfigurationError, "exists"):
            parse_pipe_config.run("/test/deeper/stream2:int8[e0,e1,e2]", self.db)
        with self.assertRaisesRegex(ConfigurationError, "exists"):
            parse_pipe_config.run("/test/deeper/stream2:int8[e0,x]", self.db)

    def test_errors_if_unconfigured_stream_not_in_db(self):
        with self.assertRaisesRegex(ConfigurationError, "configuration"):
            parse_pipe_config.run("/test/deeper/new_stream", self.db)