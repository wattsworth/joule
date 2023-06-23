import logging
import tempfile
import os
import datetime
import unittest

from tests.helpers import DbTestCase
from joule.models import (DataStream, Folder,
                          Element, Module)
from joule.services import load_modules

logger = logging.getLogger('joule')


class TestConfigureModules(DbTestCase):

    def test_parses_configs(self):
        """e2e module configuration service test"""

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

        root = Folder(name="root",
                      updated_at=datetime.datetime.now())
        root.children = [folder_test]
        self.db.add(root)

        self.db.commit()
        configs = [
            # writes to /test/stream1
            """
            [Main] 
              name = module1
              exec_cmd = runit.sh
            [Arguments]
              key = value
            # no inputs
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
            # no outputs
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
                modules = load_modules.run(conf_dir, self.db)
                output = ' '.join(logs.output)
                # log the missing stream configuration
                self.assertIn('/missing/stream', output)
                # log the incompatible stream configuration
                self.assertIn('different elements', output)
        # now check the database:
        # should have three streams
        self.assertEqual(self.db.query(DataStream).count(), 3)
        # and two modules
        self.assertEqual(len(modules), 2)
        # module1 should have no inputs and one output
        m1: Module = [m for m in modules if m.name == "module1"][0]
        self.assertEqual(len(m1.inputs), 0)
        self.assertEqual(len(m1.outputs), 1)
        self.assertEqual(m1.outputs["raw"], stream1)
        # module2 should have 1 input and 2 outputs
        m2: Module = [m for m in modules if m.name == "module2"][0]
        self.assertEqual(len(m2.inputs), 1)
        self.assertEqual(len(m2.outputs), 2)
        self.assertEqual(m2.inputs["source"], stream1)
        self.assertEqual(m2.outputs['sink1'], stream2)
        # sink2 goes to a new stream
        stream3 = self.db.query(DataStream).filter_by(name="stream3").one()
        self.assertEqual(m2.outputs['sink2'], stream3)
