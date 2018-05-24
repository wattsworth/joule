from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import unittest
import tempfile
import logging
import os

from joule.models import (Base, Stream, Folder, Element)
from joule.services import configure_streams

logger = logging.getLogger('joule')


class TestConfigureStreams(unittest.TestCase):
    def test_parses_conf_files_in_path(self):
        """parses files ending in *.conf and ignores others"""
        file_names = ['stream1.conf', 'ignored',
                      'temp.conf~', 'streamA-3.conf']

        with tempfile.TemporaryDirectory() as conf_dir:
            for name in file_names:
                # create a stub stream configuration (needed for
                # configparser)
                with open(os.path.join(conf_dir, name), 'w') as f:
                    f.write('[Main]\n')

            configs = configure_streams._load_configs(conf_dir)
        self.assertEqual(2, len(configs))
        self.assertTrue('stream1.conf' in configs.keys())
        self.assertTrue('streamA-3.conf' in configs.keys())

    def test_merges_config_and_db_streams(self):
        """e2e stream configuration service test"""
        # create a database
        engine = create_engine('sqlite://')
        Base.metadata.create_all(engine)
        session = Session(bind=engine)

        # /test/stream1:float32_3
        folder_test = Folder(name="test")
        stream1 = Stream(name="stream1", path="/test", keep_us=100,
                         datatype=Stream.DATATYPE.FLOAT32)
        stream1.elements = [Element(name="e%d" % x, index=x, default_min=1) for x in range(3)]
        folder_test.streams.append(stream1)

        # /test/deeper/stream2: int8_2
        folder_deeper = Folder(name="deeper")
        stream2 = Stream(name="stream2", path="/test/deeper", datatype=Stream.DATATYPE.INT8)
        stream2.elements = [Element(name="e%d" % x, index=x) for x in range(2)]
        folder_deeper.streams.append(stream2)

        root = Folder(name="root")
        root.children = [folder_test, folder_deeper]
        session.add(root)

        session.commit()
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
            # /new/path/stream3: uint8_2 <a new stream>
            """
            [Main]
              name = stream3
              path = /new/path
              datatype = uint8
            [Element1]
              name=1
            [Element2]
              name=2
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
                configure_streams.run(conf_dir, session)
                # log the bad path error
                self.assertRegex(logs.output[0], 'path')
                # log the incompatible layout error
                self.assertRegex(logs.output[1], 'layout')

        # now check the database:
        # should have 3 streams
        self.assertEqual(session.query(Stream).count(), 3)
        # and 7 elements (orphans eliminated)
        self.assertEqual(session.query(Element).count(), 7)
        # Check stream merging
        #   stream1 should have a new keep value
        stream1: Stream = session.query(Stream).filter_by(name="stream1").first()
        self.assertEqual(stream1.keep_us, Stream.KEEP_ALL)
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
        stream2: Stream = session.query(Stream).filter_by(name="stream2").first()
        self.assertEqual(stream2.layout, 'int8_2')
        # Check new streams are added
        stream2: Stream = session.query(Stream).filter_by(name="stream3").first()
        self.assertEqual(stream2.layout, 'uint8_2')

