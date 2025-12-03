import unittest
from unittest.mock import patch, MagicMock, AsyncMock, create_autospec
import tempfile
from joule.models.pipes import Pipe
from joule.models.data_store.data_store import DataStore
from joule.models.data_movement.targets.data_target import DataTarget, data_target_from_config, DataExportSummary
from joule.models.data_movement.exporting.exporter_state import ExporterState
from joule.models import DataStream, Element
from joule.models.pipes import interval_token as compute_interval_token
from joule.utilities.archive_tools import ImportLogger
from tests import helpers
import json
import os
from joule.models.pipes.local_pipe import LocalPipe
import numpy as np
import asyncio

ARCHIVE_PATH = os.path.join(os.path.dirname(__file__), '..','archive_data','data','0')

class TestDataTarget(unittest.IsolatedAsyncioTestCase):       

    async def test_data_target_from_config(self):

        export_target = data_target_from_config({
            "source_label": "test",
            "path": "/some/path/to/data",
            "decimation_factor": 4
        }, type="exporter")
        self.assertEqual(export_target.source_label, "test")
        self.assertEqual(export_target.path, "/some/path/to/data")

        import_target = data_target_from_config({
            "source_label": "test",
            "path": "/some/path/to/data",
            "merge_gap": "10s"
        },type="importer")

        self.assertEqual(import_target.source_label, "test")
        self.assertEqual(import_target.path, "/some/path/to/data")
        self.assertEqual(import_target.merge_gap, 1e6*10)

    async def test_run_import(self):
        store = create_autospec(spec=DataStore, spec_set=True, instance=True)
        target = DataTarget(source_label="test",
                            path="/some/path/to/data")
        my_stream = DataStream(
            name="test",
            description="test_description",
            datatype=DataStream.DATATYPE.FLOAT32,
            elements=[Element(name="0",index=0), Element(name="1", index=1)])
        find_stream_by_path = MagicMock(return_value=my_stream)

        with open(os.path.join(ARCHIVE_PATH,'metadata.json'),'r') as f:
            metadata = json.load(f)['stream_model']
        importer_pipe = None
        async def mock_spawn_inserter(stream: 'DataStream', pipe:Pipe, insert_period=0):
            nonlocal importer_pipe
            importer_pipe = pipe
            return asyncio.sleep(0) # a stub co-routine since spawn_inserter returns the insertion task
             
        store.spawn_inserter = mock_spawn_inserter
        logger = ImportLogger()
        with(patch("joule.models.data_movement.targets.data_target.find_stream_by_path",
             find_stream_by_path)):
            await target.run_import(db="db_object", #not used, mocked by find_stream_by_path
                                    store=store,
                                    metadata=metadata,
                                    source_directory=os.path.join(ARCHIVE_PATH,'data'),
                                    logger=logger)

        data = importer_pipe.read_nowait()
        self.assertEqual(len(data),70) # make sure the pipe received all the data
        self.assertTrue(logger.success)
        # TODO use an archive with interval breaks
            

    async def test_run_export(self):
        
        LENGTH = 500
        
        my_stream = DataStream(
            name="test",
            description="test_description",
            datatype=DataStream.DATATYPE.INT64,
            elements=[Element(name="0",index=0), Element(name="1", index=1)])
        data_chunk1 = helpers.create_data(my_stream.layout, length=LENGTH)
        data_chunk2 = helpers.create_data(my_stream.layout, length=LENGTH, 
                                          start = data_chunk1['timestamp'][-1]+100)
        my_stream.touch()
        target = DataTarget(source_label="test",
                            path="/some/path/to/data")

        find_stream_by_path = MagicMock(return_value=my_stream)
        store = create_autospec(spec=DataStore, spec_set=True, instance=True)

        async def mock_extract(stream: 'DataStream', start, end,
                      callback,  max_rows, decimation_level):
            self.assertEqual(start,95) # make sure the last_ts made it through to the extract function
            data_chunk1_w_interval = np.hstack((data_chunk1, compute_interval_token(my_stream.layout)))
            await callback(data_chunk1_w_interval, my_stream.layout, 1)
            await callback(data_chunk2, my_stream.layout, 1)
             
        store.extract = mock_extract
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
                                     my_stream.to_json())
                self.assertEqual(metadata['stream_path'], "/some/path/to/data")

            # check that data files were created correctly,
            # chunks are named <last_timestamp>.dat
            # intervals are <timestamp>_interval_break.dat
            with open(work_path + f"/data/{data_chunk1['timestamp'][-1]}.dat", 'rb') as f:
                data = np.load(f)
                np.testing.assert_array_equal(data, data_chunk1)

            with open(work_path + f"/data/{data_chunk2['timestamp'][-1]}.dat", 'rb') as f:
                data = np.load(f)
                np.testing.assert_array_equal(data, data_chunk2)

            # make sure the interval break file was created
            self.assertTrue(os.path.exists(work_path + f"/data/{data_chunk1['timestamp'][-1]+1}_interval_break.dat"))
            
            # check the return value
            self.assertEqual(new_state.last_timestamp, data_chunk2['timestamp'][-1]+1)

    async def test_summarizes_export(self):
        target = DataTarget(source_label="test",
                             path="/some/path/to/events") 
        my_stream = DataStream(
            name="test",
            description="test_description",
            datatype=DataStream.DATATYPE.INT64,
            elements=[Element(name="0",index=0), Element(name="1", index=1)])
        # null response when there is no export summary
        summary = target.summarize_export()
        self.assertEqual({}, summary)
        # this is created by the run function, manually create it for testing
        target.export_summary = DataExportSummary(row_count=100,interval_count=1)
        # when the start or end ts are blank this does not create an error
        summary = target.summarize_export()
        self.assertEqual(summary['source_label'],target.source_label)
        self.assertIsNone(summary['start_ts'])
        self.assertIsNone(summary['end_ts'])
        # uses start_ts and end_ts if available
        target.export_summary.start_ts=0
        target.export_summary.end_ts=100
        summary = target.summarize_export()
        self.assertEqual(summary['source_label'],target.source_label)
        self.assertEqual(summary['start_ts'],0)
        self.assertEqual(summary['end_ts'],100)