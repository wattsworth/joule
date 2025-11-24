import unittest
from unittest.mock import patch, MagicMock, AsyncMock, create_autospec
import tempfile
from joule.models.data_movement.targets.event_target import EventTarget, ON_EVENT_CONFLICT, event_target_from_config, EventExportSummary
from joule.models.data_movement.exporting.exporter_state import ExporterState
from joule.models import EventStream
from joule.models.data_store.event_store import EventStore
from tests import helpers
from joule.utilities.archive_tools import ImportLogger
import json
import os
from joule.models.pipes.local_pipe import LocalPipe
import numpy as np
 

ARCHIVE_PATH = os.path.join(os.path.dirname(__file__), '..','archive_data','events','0')

class TestEventTarget(unittest.IsolatedAsyncioTestCase):
        

    async def test_event_target_export(self):
        event_stream = EventStream(name="test",description="test stream", 
                                   event_fields={"name":"string"})
        event_stream.touch()
        target = EventTarget(source_label="test",
                            path="/some/path/to/data",
                            on_conflict=ON_EVENT_CONFLICT.NA,
                            filter = [[["name","eq","test"]]])
        find_stream_by_path = MagicMock(return_value=event_stream)
        store = create_autospec(spec=EventStore, spec_set=True, instance=True)
        event_records = [{"id": i,
                         "start_time":i*10+1000,
                         "end_time":i*10+2+1000,
                         "event_stream_id": -1,
                         "content": {"test":"value"}
                         } for i in range(20)]
        block1 = event_records[:10]
        block2 = event_records[10:]
        store.extract = AsyncMock(side_effect=[block1,block2,[]])
        with(
            tempfile.TemporaryDirectory() as work_path,
            patch("joule.models.data_movement.targets.event_target.find_stream_by_path",
                           find_stream_by_path)):
            new_state = await target.run_export(db="db_object", #not used, mocked by find_stream_by_path
                                    store=store,
                                    work_path=work_path,
                                    state=ExporterState(last_timestamp=1000))
            # list the contents of work_path/data, should be 2 items
            # each of these is tested below
            contents = os.listdir(work_path+"/data")
            self.assertEqual(len(contents), 2)

            # check the metadata file
            with open(work_path + '/metadata.json', 'r') as f:
                metadata = json.loads(f.read())
                self.assertDictEqual(metadata['stream_model'],
                                     event_stream.to_json())
                self.assertEqual(metadata['stream_path'], "/some/path/to/data")

            # check that data files were created correctly,
            # chunks are named <last_timestamp>.dat
            # intervals are <timestamp>_interval_break.dat
            with open(work_path + f"/data/{block1[-1]['start_time']}.json", 'rb') as f:
                data = json.load(f)
                np.testing.assert_array_equal(data, block1)

            with open(work_path + f"/data/{block2[-1]['start_time']}.json", 'rb') as f:
                data = json.load(f)
                np.testing.assert_array_equal(data, block2)

            # check the return value
            self.assertEqual(new_state.last_timestamp, block2[-1]['start_time']+1)

            # check the parameters to the data read call
            store.extract.assert_called_with(event_stream, 
                                             start=1191, end=None,
                                             json_filter= [[["name","eq","test"]]],
                                             limit=1000,
                                             include_on_going_events=False)

    async def test_run_import(self):
        store = create_autospec(spec=EventStore, spec_set=True, instance=True)
        target = EventTarget(source_label="test",
                             path="/some/path/to/events",
                             on_conflict=ON_EVENT_CONFLICT.KEEP_BOTH,
                             filter=None) # filter not used on imports
        my_stream = EventStream(
            name="test",
            description="test_description")
        find_stream_by_path = MagicMock(return_value=my_stream)

        with open(os.path.join(ARCHIVE_PATH,'metadata.json'),'r') as f:
            metadata = json.load(f)['stream_model']
        logger = ImportLogger()
        with(patch("joule.models.data_movement.targets.event_target.find_stream_by_path",
                   find_stream_by_path)):
            await target.run_import(db="db_object", #not used
                                    store=store,
                                    metadata=metadata,
                                    source_directory=os.path.join(ARCHIVE_PATH,'data'),
                                    logger=logger)

    async def test_summarizes_export(self):
        target = EventTarget(source_label="test",
                             path="/some/path/to/events",
                             on_conflict=ON_EVENT_CONFLICT.KEEP_BOTH,
                             filter=None) # filter not used on imports
        event_stream = EventStream(name="test",description="test stream", 
                                   event_fields={"name":"string"})
        # null response when there is no export summary
        summary = target.summarize_export()
        self.assertEqual({}, summary)
        # this is created by the run function, manually create it for testing
        target.export_summary = EventExportSummary(event_fields=event_stream.event_fields)
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

    async def test_event_target_from_config(self):
        export_target = event_target_from_config({
            "source_label": "test",
            "path": "/some/path/to/data",
            "filter": json.dumps([[["device","like","test%%"]]])
        }, type="exporter")
        self.assertEqual(export_target.source_label,"test")
        self.assertEqual(export_target.path,"/some/path/to/data")
        self.assertEqual(export_target.filter, [[["device","like","test%%"]]])
        # filter is optional
        export_target = event_target_from_config({
            "source_label": "test",
            "path": "/some/path/to/data",
        }, type="exporter")
        self.assertEqual(export_target.source_label,"test")
        self.assertEqual(export_target.path,"/some/path/to/data")
        self.assertIsNone(export_target.filter)

        # test the different on_conflict settings
        for str_val, enum_val in [('keep_source',ON_EVENT_CONFLICT.KEEP_SOURCE),
                                  ('keep_destination',ON_EVENT_CONFLICT.KEEP_DESTINATION),
                                  ('keep_both',ON_EVENT_CONFLICT.KEEP_BOTH),
                                  ('merge',ON_EVENT_CONFLICT.MERGE)]:
            import_target = event_target_from_config({
                "source_label": "test",
                "path": "/some/path/to/data",
                "on_conflict":str_val
            }, type="importer")
            self.assertEqual(import_target.on_conflict,enum_val)
        with self.assertRaises(ValueError):
            event_target_from_config({
                "source_label": "test",
                "path": "/some/path/to/data",
                "on_conflict":"invalid"
            }, type="importer")
            

