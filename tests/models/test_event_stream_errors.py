import unittest
import datetime
from joule.models import (EventStream, Folder, event_stream)
from joule.models.data_store.event_store import StreamInfo
from joule.errors import ConfigurationError
from tests import helpers


class TestStream(unittest.TestCase):
    def setUp(self):
        pass

    def test_attribute_errors(self):
        my_stream = EventStream(name='test',
                                updated_at=datetime.datetime.now())
        for bad_val in ['abc', -2, [], {}, (1, 2, 3)]:
            with self.assertRaisesRegex(ConfigurationError, 'keep'):
                my_stream.update_attributes({"keep_us": bad_val})

        for bad_val in ['abc', -1, [], {}, (1, 2, 3)]:
            with self.assertRaisesRegex(ConfigurationError, 'chunk_duration') as error:
                my_stream.update_attributes({"chunk_duration_us": bad_val})

        for bad_val in ['abc', -1, [], (1, 2, 3), {'field1': 'incorrect'}]:
            with self.assertRaisesRegex(ConfigurationError, 'event_fields') as error:
                my_stream.update_attributes({"event_fields": bad_val})

        for bad_val in ['/invalid', '', 'also/invalid']:
            with self.assertRaisesRegex(ConfigurationError, 'name') as error:
                my_stream.update_attributes({"name": bad_val})
