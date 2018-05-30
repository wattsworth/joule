from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import unittest
import logging
import tempfile
import os
from joule.models import (Base, Stream, Folder,
                          Element, Module, Pipe)
from joule.services import configure_modules

logger = logging.getLogger('joule')


class TestConfigureModules(unittest.TestCase):

    def test_parses_configs(self):
        """e2e module configuration service test"""
        # create a database
        engine = create_engine('sqlite://')
        Base.metadata.create_all(engine)
        session = Session(bind=engine)

        # /test/stream1:float32_3
        folder_test = Folder(name="test")
        stream1 = Stream(name="stream1", keep_us=100,
                         datatype=Stream.DATATYPE.FLOAT32)
        stream1.elements = [Element(name="e%d" % x, index=x, default_min=1) for x in range(3)]
        folder_test.streams.append(stream1)

        # /test/deeper/stream2: int8_2
        folder_deeper = Folder(name="deeper")
        stream2 = Stream(name="stream2", datatype=Stream.DATATYPE.INT8)
        stream2.elements = [Element(name="e%d" % x, index=x) for x in range(2)]
        folder_deeper.streams.append(stream2)
        folder_deeper.parent = folder_test

        root = Folder(name="root")
        root.children = [folder_test]
        session.add(root)

        session.commit()
        configs = [
            # writes to /test/stream1
            """
            [Main] 
              name = module1
              exec_cmd = runit.sh
            [Arguments]
              key = value
            [Inputs]
              # reader
            [Outputs]
              raw = /test/stream1
            """,
            # reads from /test/stream1, writes to /test/deeper/stream2 and /test/stream3
            """
            [Main]
              name = module2
              exec_cmd = runit2.sh
            [Inputs]
              source = /test/stream1:float32[e0,e1, e2]
            [Outputs]
              sink1 = /test/deeper/stream2
              sink2 = /test/stream3:uint8[ x, y ]
            """,
            # ignored: unconfigured input
            """
            [Main]
              name = bad_module
              exec_cmd = runit3.sh
            [Inputs]
              source = /missing/stream
            [Outputs]
            """,
            # ignored: mismatched stream config
            """
            [Main] 
              name = bad_module2
              exec_cmd = runit4.sh
            [Inputs]
              source = /test/stream3:uint8[x,y,z]
            [Outputs]
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
                configure_modules.run(conf_dir, session)
                # log the missing stream configuration
                self.assertRegex(logs.output[0], '/missing/stream')
                # log the incompatible stream configuration
                self.assertRegex(logs.output[1], 'different elements')
        # now check the database:
        # should have three streams
        self.assertEqual(session.query(Stream).count(), 3)
        # and two modules
        self.assertEqual(session.query(Module).count(), 2)
        # module1 should have no inputs and one output
        m1: Module = session.query(Module).filter_by(name="module1").one()
        self.assertEqual(len(m1.pipes), 1)
        p_raw: Pipe = m1.pipes[0]
        self.assertEqual(p_raw.name, 'raw')
        self.assertEqual(p_raw.stream, stream1)
        # module2 should have 1 input and 2 outputs
        m2: Module = session.query(Module).filter_by(name="module2").one()
        self.assertEqual(len(m2.inputs), 1)
        self.assertEqual(len(m2.outputs), 2)
        p_source: Pipe = [p for p in m2.inputs if p.name == 'source'][0]
        self.assertEqual(p_source.stream, stream1)
        p_sink1 = [p for p in m2.outputs if p.name == 'sink1'][0]
        self.assertEqual(p_sink1.stream, stream2)
        # sink2 goes to a new stream
        stream3 = session.query(Stream).filter_by(name="stream3").one()
        p_sink2 = [p for p in m2.outputs if p.name == 'sink2'][0]
        self.assertEqual(p_sink2.stream, stream3)
