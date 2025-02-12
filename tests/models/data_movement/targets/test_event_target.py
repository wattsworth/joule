import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import tempfile
from joule.models.data_movement.targets.event_target import EventTarget, ON_EVENT_CONFLICT, event_target_from_config
from joule.models.data_movement.exporting.exporter_state import ExporterState
from joule.models import EventStream
from tests import helpers
import json
import os
from joule.models.pipes.local_pipe import LocalPipe
import numpy as np

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
        store = MagicMock()
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
            store.extract.assert_called_with(start=1191,limit=1000,filter= [[["name","eq","test"]]])

    async def test_event_target_from_config(self):
        export_target = event_target_from_config({
            "source_label": "test",
            "path": "/some/path/to/data",
            "filter": json.dumps([[["device","like","test%%"]]])
        }, type="exporter")
        self.assertEqual(export_target.source_label,"test")
        self.assertEqual(export_target.path,"/some/path/to/data")
        self.assertEqual(export_target.filter, [[["device","like","test%%"]]])

    async def test_event_target(self):
        pass