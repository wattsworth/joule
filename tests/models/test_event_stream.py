import unittest
import datetime
from joule.models import (EventStream, Folder, event_stream)
from joule.models.data_store.event_store import StreamInfo


class TestStream(unittest.TestCase):
    def setUp(self):
        pass

    def test_attributes(self):
        my_folder = Folder(name="test")
        my_stream = EventStream(name='test', description='a test',
                                event_fields={'field1': 'string', 'field2': 'numeric'},
                                keep_us=100,
                                chunk_duration_us=0,
                                updated_at=datetime.datetime.now())
        my_stream.folder = my_folder
        new_attrs = {
            "name": "new_n",
            "description": "new_d",
            "event_fields": {"test_val": "string"},
            "keep_us": 1000,
            "chunk_duration_us": 100
        }
        last_update = my_stream.updated_at
        my_stream.update_attributes(new_attrs)
        # make sure all attributes are updated
        self.assertEqual(my_stream.name, new_attrs["name"])
        self.assertEqual(my_stream.description, new_attrs["description"])
        self.assertEqual(my_stream.chunk_duration_us, new_attrs["chunk_duration_us"])
        self.assertEqual(my_stream.event_fields, new_attrs["event_fields"])
        # the updated at should be more recent
        self.assertGreater(my_stream.updated_at, last_update)

        # touching also increments the updated_at
        last_update = my_stream.updated_at
        my_stream.touch()
        self.assertGreater(my_stream.updated_at, last_update)
        self.assertEqual(my_stream.updated_at, my_folder.updated_at)

    def test_representations(self):
        my_stream = EventStream(name='test', description='a test',
                                event_fields={'field1': 'string', 'field2': 'numeric'},
                                keep_us=100,
                                chunk_duration_us=0,
                                updated_at=datetime.datetime.now())
        json_resp = my_stream.to_json()
        self.assertEqual(json_resp["name"], my_stream.name)
        self.assertEqual(json_resp["description"], my_stream.description)
        self.assertEqual(json_resp["updated_at"], my_stream.updated_at.isoformat())
        self.assertEqual(json_resp["keep_us"], my_stream.keep_us)
        self.assertEqual(json_resp["chunk_duration_us"], my_stream.chunk_duration_us)
        self.assertDictEqual(json_resp['event_fields'], my_stream.event_fields)

        # has a string representation
        self.assertTrue(my_stream.name in str(my_stream))

        # can be recovered from JSON
        new_stream = event_stream.from_json(json_resp)
        self.assertEqual(new_stream.name, my_stream.name)
        self.assertEqual(new_stream.description, my_stream.description)
        # updated_at is not serialized, instead it is set to now
        self.assertGreater(new_stream.updated_at, my_stream.updated_at)
        self.assertEqual(new_stream.keep_us, my_stream.keep_us)
        self.assertEqual(new_stream.chunk_duration_us, my_stream.chunk_duration_us)
        self.assertDictEqual(new_stream.event_fields, my_stream.event_fields)

    def test_handles_stream_info(self):
        my_stream = EventStream(name='test', description='a test',
                                event_fields={'field1': 'string', 'field2': 'numeric'},
                                keep_us=100,
                                chunk_duration_us=0,
                                updated_at=datetime.datetime.now())
        my_stream.id = 100
        stream_info = StreamInfo(start=0, end=100, event_count=10, total_time=100, bytes=100)
        json_resp = my_stream.to_json(info={my_stream.id: stream_info})
        self.assertDictEqual(json_resp['data_info'], stream_info.to_json())

        # ignored when info is not available
        json_resp = my_stream.to_json(info={101: stream_info})
        self.assertFalse('data_info' in json_resp)

