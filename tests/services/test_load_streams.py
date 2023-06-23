from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import unittest
import tempfile
import logging
import os
import warnings
import datetime

from tests.helpers import DbTestCase
from joule.models import (Base, DataStream, Folder, Element)
from joule.services import load_streams

logger = logging.getLogger('joule')

warnings.simplefilter('always')


class TestConfigureStreams(DbTestCase):

    def test_merges_config_and_db_streams(self):
        """e2e stream configuration service test"""

        # /test/stream1:float32_3
        folder_test = Folder(name="test",
                             updated_at=datetime.datetime.now())
        stream1 = DataStream(name="stream1", keep_us=100,
                             datatype=DataStream.DATATYPE.FLOAT32,
                             updated_at=datetime.datetime.now())
        stream1.elements = [Element(name="e%d" % x, index=x, default_min=1) for x in range(3)]
        folder_test.data_streams.append(stream1)

        # /test/deeper/stream2: int8_2
        folder_deeper = Folder(name="deeper",
                               updated_at=datetime.datetime.now())
        stream2 = DataStream(name="stream2", datatype=DataStream.DATATYPE.INT8,
                             updated_at=datetime.datetime.now())
        stream2.elements = [Element(name="e%d" % x, index=x) for x in range(2)]
        folder_deeper.data_streams.append(stream2)
        folder_deeper.parent = folder_test

        # /test/deeper/stream3: int8_2
        stream3 = DataStream(name="stream3", datatype=DataStream.DATATYPE.INT16,
                             updated_at=datetime.datetime.now())
        stream3.elements = [Element(name="e%d" % x, index=x) for x in range(2)]
        folder_deeper.data_streams.append(stream3)

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
            # /new/path/stream4: uint8_2 <a new stream>
            """
            [Main]
              name = stream4
              path = /new/path
              datatype = uint8
            [Element1]
              name=1
            [Element2]
              name=2
            """,
            # /new/path/stream5: uint8_1 <a new stream>
            """
            [Main]
              name = stream5
              path = /new/path
              datatype = uint8
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
              datatype = uint8
              keep = all
            [Element1]
              name=e1
            """,
        ]
        with tempfile.TemporaryDirectory() as conf_dir:
            # write the configs in 0.conf, 1.conf, ...
            i = 0
            for conf in configs:
                with open(os.path.join(conf_dir, "%d.conf" % i), 'w') as f:
                    f.write(conf)
                i += 1
            with self.assertLogs(logger=logger, level=logging.ERROR) as logs:
                load_streams.run(conf_dir, self.db)
                # log the bad path error
                self.assertRegex(logs.output[0], 'path')
                # log the incompatible layout error
                self.assertRegex(logs.output[1], 'layout')

        # now check the database:
        # should have 3 streams
        self.assertEqual(self.db.query(DataStream).count(), 5)
        # and 7 elements (orphans eliminated)
        self.assertEqual(self.db.query(Element).count(), 10)
        # Check stream merging
        #   stream1 should have a new keep value
        stream1: DataStream = self.db.query(DataStream).filter_by(name="stream1").one()
        self.assertEqual(stream1.keep_us, DataStream.KEEP_ALL)
        #   its elements should have new attributes
        self.assertEqual(stream1.elements[0].name, 'new_e1')
        self.assertEqual(stream1.elements[0].display_type, Element.DISPLAYTYPE.DISCRETE)
        self.assertEqual(stream1.elements[0].default_min, None)
        self.assertEqual(stream1.elements[1].name, 'new_e2')
        self.assertEqual(stream1.elements[1].display_type, Element.DISPLAYTYPE.EVENT)
        self.assertEqual(stream1.elements[1].default_min, None)
        self.assertEqual(stream1.elements[2].name, 'new_e3')
        self.assertEqual(stream1.elements[2].default_min, -10)
        # Check unconfigured streams are unchanged
        #   /test/deeper/stream2 should be the same
        stream2: DataStream = self.db.query(DataStream).filter_by(name="stream2").one()
        self.assertEqual(stream2.layout, 'int8_2')
        #   /test/deeper/stream3 should be the same
        stream3: DataStream = self.db.query(DataStream).filter_by(name="stream3").one()
        self.assertEqual(stream3.layout, 'int16_2')
        # Check new streams are added
        stream4: DataStream = self.db.query(DataStream).filter_by(name="stream4").one()
        self.assertEqual(stream4.layout, 'uint8_2')

        # Check the folder structure
        # -root
        #  -test
        #    -[stream1]
        #    -deeper
        #      -[stream2]
        #  -new
        #    -path
        #      -[stream3]
        self.assertEqual(len(root.children), 2)
        for f in root.children:
            if f.name == 'test':
                self.assertEqual(len(f.data_streams), 1)
                self.assertEqual(f.data_streams[0].name, 'stream1')
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
                    self.assertTrue(stream.name in ['stream4', 'stream5'])
            else:
                self.fail("unexpected name: " + f.name)
