from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import json
import tempfile
import logging
import os
import warnings
import datetime

from tests.helpers import DbTestCase
from joule.models import (DataStream, EventStream, Folder, Element)
from joule.services import load_data_streams, load_event_streams

logger = logging.getLogger('joule')

warnings.simplefilter('always')


class TestConfigureStreams(DbTestCase):

    def test_merges_config_and_db_streams(self):
        """e2e stream configuration service test, covers both data and event streams"""

        # /test/stream1:float32_3
        folder_test = Folder(name="test",
                             updated_at=datetime.datetime.now())
        stream1 = DataStream(name="stream1", keep_us=100,
                             datatype=DataStream.DATATYPE.FLOAT32,
                             updated_at=datetime.datetime.now())
        stream1.elements = [Element(name="e%d" % x, index=x, default_min=1) for x in range(3)]
        folder_test.data_streams.append(stream1)

        # /test/event1:[name:string]
        event1 = EventStream(name="event1", keep_us=100, description="event1 original description",
                             event_fields={"name": "string"},
                             updated_at=datetime.datetime.now())
        folder_test.event_streams.append(event1)

        # /test/deeper/stream2: int16_2
        folder_deeper = Folder(name="deeper",
                               updated_at=datetime.datetime.now())
        stream2 = DataStream(name="stream2", datatype=DataStream.DATATYPE.INT16,
                             updated_at=datetime.datetime.now())
        stream2.elements = [Element(name="e%d" % x, index=x) for x in range(2)]
        folder_deeper.data_streams.append(stream2)
        folder_deeper.parent = folder_test

        # /test/deeper/stream3: int16_2
        stream3 = DataStream(name="stream3", datatype=DataStream.DATATYPE.INT16,
                             updated_at=datetime.datetime.now())
        stream3.elements = [Element(name="e%d" % x, index=x) for x in range(2)]
        folder_deeper.data_streams.append(stream3)

        # /test/deeper/event2:[category:["cat1","cat2"]]
        event2 = EventStream(name="event2", keep_us=100, description="event2 original description",
                             event_fields={"category": json.dumps(['cat1','cat2'])},
                             updated_at=datetime.datetime.now())
        folder_deeper.event_streams.append(event2)
        root = Folder(name="root",
                      updated_at=datetime.datetime.now())
        root.children = [folder_test]
        self.db.add(root)

        self.db.commit()
        configs = [
            # /test/stream1:float32_3 <different element configs and keep>
            """
            [Main] 
              name = stream1
              path = /test
              datatype = float32
              keep = all
            [Element1]
              name=new_e1
              display_type=discrete
            [Element2]
              name=new_e2
              display_type=event
            [Element3]
              name=new_e3
              default_min=-10
            """,
            # /new/path/stream4: int16_2 <a new stream>
            """
            [Main]
              name = stream4
              path = /new/path
              datatype = int16
            [Element1]
              name=1
            [Element2]
              name=2
            """,
            # /new/path/stream5: int16_1 <a new stream>
            """
            [Main]
              name = stream5
              path = /new/path
              datatype = int16
            [Element1]
              name=1
            """,
            # /test/deeper/stream2: float32_1 <conflicting layout>
            """
            [Main]
              name = stream2
              path = /test/deeper
              datatype = float32
            [Element1]
              name = 1
            """,
            # /invalid path//invalid: int64_1 <invalid config (ignored)>
            """
            [Main] 
              name = invalid
              path = /invalid path//
              datatype = int16
              keep = all
            [Element1]
              name=e1
            """,
            # /test/event1 <invalid, conflicts with event stream name>
            """
            [Main]
              name = event1
              path = /test
              datatype = int16
            [Element1]
              name=e1
            """
        ]
        # write the data streams and parse them
        with tempfile.TemporaryDirectory() as conf_dir:
            # write the configs in 0.conf, 1.conf, ...
            i = 0
            for conf in configs:
                with open(os.path.join(conf_dir, "%d.conf" % i), 'w') as f:
                    f.write(conf)
                i += 1
            with self.assertLogs(logger=logger, level=logging.ERROR) as logs:
                load_data_streams.run(conf_dir, self.db)
                # log the bad path error
                self.assertRegex(logs.output[0], 'path')
                # log the name conflict error
                self.assertRegex(logs.output[1], 'existing event stream')
                # log the incompatible layout error
                self.assertRegex(logs.output[2], 'layout')
        event_configs = [
            # /test/event1:[name:string,age:numeric] <different keep, description>
            """
            [Main] 
              name = event1
              path = /test
              description = updated
              keep = 1w
            [Field1]
              name=name
              type=string
            [Field2]
              name=weight
              type=numeric
            """,
            """
            [Main] 
              name = event4
              path = /test
              description = new
              keep = 1w
            [Field1]
              name=name
              type=string
            [Field2]
              name=weight
              type=numeric
            """,
            """
            [Main] 
              name = event3
              path = /other/new
              description = new stream
              keep = all
            [Field1]
              name=fruits
              type=category:["apple", "banana"]
            """,
            # invalid config, name conflict with data stream
            """
            [Main] 
              name = stream1
              path = /test
              description = invalid- conflicts with data stream name
              keep = all
            [Field1]
              name=fruits
              type=category:["apple", "banana"]
            """
        ]
        with tempfile.TemporaryDirectory() as conf_dir:
          # write the configs in 0.conf, 1.conf, ...
          i = 0
          for conf in event_configs:
            with open(os.path.join(conf_dir, "%d.conf" % i), 'w') as f:
              f.write(conf)
            i += 1
          with self.assertLogs(logger=logger, level=logging.ERROR) as logs:
            load_event_streams.run(conf_dir, self.db)
            # log the name conflict error
            self.assertRegex(logs.output[0], 'existing data stream')

        # now check the database:

        # ======= Data Streams =======

        # should have 5 data streams
        self.assertEqual(self.db.query(DataStream).count(), 5)
        # and 10 elements (orphans eliminated)
        self.assertEqual(self.db.query(Element).count(), 10)
        # Check stream merging
        #   stream1 should have a new keep value
        stream1: DataStream = self.db.query(DataStream).filter_by(name="stream1").one()
        self.assertEqual(stream1.keep_us, DataStream.KEEP_ALL)
        self.assertTrue(stream1.is_configured)
        #   its elements should have new attributes
        self.assertEqual(stream1.elements[0].name, 'new_e1')
        self.assertEqual(stream1.elements[0].display_type, Element.DISPLAYTYPE.DISCRETE)
        self.assertIsNone(stream1.elements[0].default_min)
        self.assertEqual(stream1.elements[1].name, 'new_e2')
        self.assertEqual(stream1.elements[1].display_type, Element.DISPLAYTYPE.EVENT)
        self.assertIsNone(stream1.elements[1].default_min)
        self.assertEqual(stream1.elements[2].name, 'new_e3')
        self.assertEqual(stream1.elements[2].default_min, -10)
        # Check unconfigured streams are unchanged
        #   /test/deeper/stream2 should be the same
        stream2: DataStream = self.db.query(DataStream).filter_by(name="stream2").one()
        self.assertEqual(stream2.layout, 'int16_2')
        self.assertFalse(stream2.is_configured)
        #   /test/deeper/stream3 should be the same
        stream3: DataStream = self.db.query(DataStream).filter_by(name="stream3").one()
        self.assertEqual(stream3.layout, 'int16_2')
        self.assertFalse(stream3.is_configured)
        # Check new streams are added
        stream4: DataStream = self.db.query(DataStream).filter_by(name="stream4").one()
        self.assertEqual(stream4.layout, 'int16_2')
        self.assertTrue(stream4.is_configured)

        # ======= Event Streams =======
        # should have 4 event streams (one modified, one unconfigured, and two new)
        self.assertEqual(self.db.query(EventStream).count(), 4)
        # check the modified stream
        event1 = self.db.query(EventStream).filter_by(name="event1").one()
        self.assertEqual(event1.keep_us, 60 * 60 * 24 * 7 * 1e6) # 1 week
        self.assertEqual(event1.description, "updated")
        self.assertEqual(event1.event_fields, {"name": "string", "weight": "numeric"})
        self.assertTrue(event1.is_configured)
        # check the unconfigured stream
        event2 = self.db.query(EventStream).filter_by(name="event2").one()
        self.assertEqual(event2.keep_us, 100)
        self.assertEqual(event2.description, "event2 original description")
        self.assertLess(event2.updated_at, event1.updated_at)
        self.assertFalse(event2.is_configured)
        # check the new streams
        event3 = self.db.query(EventStream).filter_by(name="event3").one()
        self.assertEqual(event3.keep_us, EventStream.KEEP_ALL)
        self.assertEqual(event3.description, "new stream")
        self.assertEqual(event3.event_fields, {"fruits": "category:" + json.dumps(["apple", "banana"])})
        self.assertTrue(event3.is_configured)
        event4 = self.db.query(EventStream).filter_by(name="event4").one()
        self.assertEqual(event4.name, "event4")

        # Check the folder structure
        # -root
        #  -test
        #    -[stream1]
        #    -[event1]
        #    -deeper
        #      -[stream2]
        #      -[stream3]
        #      -[event2]
        #  -new
        #    -path
        #      -[stream4]
        #      -[stream5]
        #  -other
        #    -new
        #      -[event3]
        self.assertEqual(len(root.children), 3)
        for f in root.children:
            if f.name == 'test':
                self.assertEqual(len(f.data_streams), 1)
                self.assertEqual(f.data_streams[0].name, 'stream1')
                self.assertEqual(len(f.event_streams), 2)
                self.assertListEqual(sorted([s.name for s in f.event_streams]), 
                                     ['event1','event4'])
                self.assertEqual(len(f.children), 1)
                deeper = f.children[0]
                self.assertEqual(deeper.name, "deeper")
                self.assertEqual(len(deeper.children), 0)
                self.assertEqual(len(deeper.data_streams), 2)
                self.assertEqual(deeper.data_streams[0].name, 'stream2')
                self.assertEqual(deeper.data_streams[1].name, 'stream3')
            elif f.name == 'new':
                self.assertEqual(len(f.data_streams), 0)
                self.assertEqual(len(f.children), 1)
                path = f.children[0]
                self.assertEqual(path.name, "path")
                self.assertEqual(len(path.children), 0)
                self.assertEqual(len(path.data_streams), 2)
                for stream in path.data_streams:
                    self.assertIn(stream.name, ['stream4', 'stream5'])
            elif f.name == 'other':
                self.assertEqual(len(f.children), 1)
                _new = f.children[0]
                self.assertEqual(_new.name, "new")
                self.assertEqual(len(_new.children), 0)
                self.assertEqual(len(_new.data_streams), 0)
                self.assertEqual(len(_new.event_streams), 1)
                self.assertEqual(_new.event_streams[0].name, 'event3')
            else:
                self.fail("unexpected name: " + f.name)
