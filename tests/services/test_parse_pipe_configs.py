import datetime

from tests.helpers import DbTestCase
from joule.models import (Base, DataStream, Folder,
                          Element, Follower)
from joule.errors import ConfigurationError
from joule.services import parse_pipe_config


class TestParsePipeConfig(DbTestCase):

    def setUp(self):
        super().setUp()
        # /test/stream1:float32[e0,e1,e2]
        folder_test = Folder(name="test",
                             updated_at=datetime.datetime.now())
        stream1 = DataStream(name="stream1", keep_us=100,
                             datatype=DataStream.DATATYPE.FLOAT32,
                             updated_at=datetime.datetime.now())
        stream1.elements = [Element(name="e%d" % x, index=x, default_min=1) for x in range(3)]
        folder_test.data_streams.append(stream1)

        # /test/deeper/stream2:int8[e0,e1]
        folder_deeper = Folder(name="deeper",
                               updated_at=datetime.datetime.now())
        stream2 = DataStream(name="stream2", datatype=DataStream.DATATYPE.INT8,
                             updated_at=datetime.datetime.now())
        stream2.elements = [Element(name="e%d" % x, index=x) for x in range(2)]
        folder_deeper.data_streams.append(stream2)
        folder_deeper.parent = folder_test

        root = Folder(name="root",
                      updated_at=datetime.datetime.now())
        root.children = [folder_test]

        remote_node = Follower(name="remote.node", key="api_key", location="https://remote.com:8088")
        self.db.add(root)
        self.db.add(remote_node)
        self.db.commit()

    def test_parses_new_stream_configs(self):
        my_stream = parse_pipe_config.run("/test/new_stream:int8[x,y]", self.db)
        # ensure stream entered the database
        self.assertEqual(my_stream, self.db.query(DataStream).filter_by(name="new_stream").one())
        # check stream datatype
        self.assertEqual(my_stream.datatype, DataStream.DATATYPE.INT8)
        # check elements
        self.assertEqual(len(my_stream.elements), 2)
        for elem in my_stream.elements:
            self.assertTrue(elem.name in ['x', 'y'])
        # check parent folder
        self.assertEqual(my_stream.folder.name, "test")

    def test_parses_existing_stream_configs(self):
        existing_stream = self.db.query(DataStream).filter_by(name="stream2").one()
        my_stream = parse_pipe_config.run("/test/deeper/stream2:int8[e0,e1]", self.db)
        # retrieved the existsing stream from the database
        self.assertEqual(my_stream, existing_stream)

    def test_parses_links_to_existing_configs(self):
        existing_stream = self.db.query(DataStream).filter_by(name="stream2").one()
        my_stream = parse_pipe_config.run("/test/deeper/stream2", self.db)
        # retrieved the existsing stream from the database
        self.assertEqual(my_stream, existing_stream)

    def test_parses_remote_stream_configs(self):
        my_stream = parse_pipe_config.run("remote.node /path/to/stream:float32[x,y]", self.db)
        self.assertTrue(my_stream.is_remote)
        self.assertEqual(my_stream.remote_node, "remote.node")
        self.assertEqual(my_stream.remote_path, "/path/to/stream")

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
        with self.assertRaisesRegex(ConfigurationError, "/test/deeper/new_stream"):
            parse_pipe_config.run("/test/deeper/new_stream", self.db)
