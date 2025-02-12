import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import tempfile
from joule.models.data_movement.targets.data_target import DataTarget, data_target_from_config
from joule.models.data_movement.exporting.exporter_state import ExporterState
from joule.models import DataStream, Element
from tests import helpers
import json
import os
from joule.models.pipes.local_pipe import LocalPipe
import numpy as np

class TestDataTarget(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        LAYOUT = "int64_2"
        LENGTH = 500
        self.chunk1 = helpers.create_data(LAYOUT, length=LENGTH)
        self.chunk2 = helpers.create_data(LAYOUT, length=LENGTH, 
                                     start = self.chunk1['timestamp'][-1]+100)
        self.my_pipe = LocalPipe("int64_2")
        self.my_pipe.write_nowait(self.chunk1)
        self.my_pipe.close_interval_nowait()
        self.my_pipe.write_nowait(self.chunk2)
        self.my_pipe.close_nowait()

        self.my_stream = DataStream(
            name="test",
            description="test_description",
            datatype=DataStream.DATATYPE.INT64,
            elements=[Element(name="0",index=0), Element(name="1", index=1)])
        self.my_stream.touch()

    async def test_data_target_from_config(self):

        export_target = data_target_from_config({
            "source_label": "test",
            "path": "/some/path/to/data",
            "decimation_factor": 4
        })
        self.assertEqual(export_target.source_label, "test")
        self.assertEqual(export_target.path, "/some/path/to/data")

        import_target = data_target_from_config({
            "source_label": "test",
            "path": "/some/path/to/data",
            "merge_gap": "10s"
        })

        self.assertEqual(import_target.source_label, "test")
        self.assertEqual(import_target.path, "/some/path/to/data")
        self.assertEqual(import_target.merge_gap, 1e6*60*10)

    async def test_data_target(self):
        target = DataTarget(source_label="test",
                            path="/some/path/to/data")

        find_stream_by_path = MagicMock(return_value=self.my_stream)
        store = MagicMock()
        store.data_read = AsyncMock(return_value=self.my_pipe)
        with(
            tempfile.TemporaryDirectory() as work_path,
            patch("joule.models.data_movement.targets.data_target.find_stream_by_path",
                           find_stream_by_path)):
            new_state = await target.run_export(db="db_object", #not used, mocked by find_stream_by_path
                                    store=store,
                                    work_path=work_path,
                                    state=ExporterState(last_timestamp=95))
            # list the contents of the work_path, should be 3 items
            # each of these is tested below
            contents = os.listdir(work_path+"/data")
            self.assertEqual(len(contents), 3)
            # check that mocks were called with correct parameters

            # check the metadata file
            with open(work_path + '/metadata.json', 'r') as f:
                metadata = json.loads(f.read())
                self.assertDictEqual(metadata['stream_model'],
                                     self.my_stream.to_json())
                self.assertEqual(metadata['stream_path'], "/some/path/to/data")

            # check that data files were created correctly,
            # chunks are named <last_timestamp>.dat
            # intervals are <timestamp>_interval_break.dat
            with open(work_path + f"/data/{self.chunk1['timestamp'][-1]}.dat", 'rb') as f:
                data = np.load(f)
                np.testing.assert_array_equal(data, self.chunk1)

            with open(work_path + f"/data/{self.chunk2['timestamp'][-1]}.dat", 'rb') as f:
                data = np.load(f)
                np.testing.assert_array_equal(data, self.chunk2)

            # make sure the interval break file was created
            self.assertTrue(os.path.exists(work_path + f"/data/{self.chunk1['timestamp'][-1]+1}_interval_break.dat"))
            
            # check the return value
            self.assertEqual(new_state.last_timestamp, self.chunk2['timestamp'][-1]+1)

            # check the parameters to the data read call
            store.data_read.assert_called_with(start=95)