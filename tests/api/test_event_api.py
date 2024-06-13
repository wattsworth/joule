from tests.api import mock_session
import random
import unittest

from joule.api.node import TcpNode
from joule import errors

from joule.api.data_stream import DataStream
from joule.models.data_store.event_store import StreamInfo
from joule.api.event_stream import EventStream, Event
from joule.api.folder import Folder
from joule.errors import ApiError
from .helpers import build_stream


class TestEventApi(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        # no URL or event loop
        self.node = TcpNode('mock_node', 'http://url', 'api_key')
        self.session = mock_session.MockSession()
        self.node.session = self.session

    async def test_event_equality(self):
        self.assertNotEqual(Event(0, 1, content={'a': 'b'}), Event(10, 11, content={'b': 'c'}))
        self.assertEqual(Event(20, 30, content={'a': 'b'}), Event(20, 30, content={'a': 'b'}))

    async def test_deletes_event_streams(self):
        # can delete by ID
        await self.node.event_stream_delete(1)
        self.assertEqual(self.session.method, 'DELETE')
        self.assertEqual(self.session.path, "/event.json")
        self.assertEqual(self.session.request_data, {'id': 1})
        # can delete by path
        await self.node.event_stream_delete('/a/path')
        self.assertEqual(self.session.method, 'DELETE')
        self.assertEqual(self.session.path, "/event.json")
        self.assertEqual(self.session.request_data, {'path': '/a/path'})

        # can delete by Folder
        src = EventStream()
        src.id = 1
        await self.node.event_stream_delete(src)
        self.assertEqual(self.session.method, 'DELETE')
        self.assertEqual(self.session.path, "/event.json")
        self.assertEqual(self.session.request_data, {'id': 1})

        # handles errors
        with self.assertRaises(errors.ApiError):
            await self.node.event_stream_delete([1, 2, 3])

    async def test_creates_event_streams(self):
        src = EventStream(name="test")
        folder = Folder(name="test")
        folder.id = 1
        src_returned = EventStream(name="test")
        src_returned.id = 100
        self.session.response_data = src_returned.to_json()

        # creates with a folder object
        await self.node.event_stream_create(src, folder)
        self.assertEqual(self.session.method, 'POST')
        self.assertEqual(self.session.path, "/event.json")
        self.assertEqual(self.session.request_data, {'stream': src.to_json(),
                                                     'dest_id': 1})

        # creates with a folder ID
        await self.node.event_stream_create(src, 10)
        self.assertEqual(self.session.request_data, {'stream': src.to_json(),
                                                     'dest_id': 10})

        # creates with a folder path
        await self.node.event_stream_create(src, "/a/path")
        self.assertEqual(self.session.request_data, {'stream': src.to_json(),
                                                     'dest_path': "/a/path"})

    async def test_gets_event_stream_info(self):
        src = EventStream(name="test")
        src.id = 10
        info = StreamInfo(start=0, end=101, event_count=102, total_time=103, bytes=0)
        self.session.response_data = {'data_info': info.to_json()}

        # gets the info by stream object
        info_returned = await self.node.event_stream_info(src)
        self.assertEqual(self.session.method, 'GET')
        self.assertEqual(self.session.path, "/event.json")
        self.assertEqual(self.session.request_data, {'id': 10})
        self.assertEqual(info.start, info_returned.start)
        self.assertEqual(info.end, info_returned.end)
        self.assertEqual(info.event_count, info_returned.event_count)
        self.assertEqual(info.total_time, info_returned.total_time)
        self.assertEqual(info.bytes, info_returned.bytes)

        # gets the info by id
        await self.node.event_stream_info(20)
        self.assertEqual(self.session.request_data, {'id': 20})

        # gets the info by path
        await self.node.event_stream_info("/a/path")
        self.assertEqual(self.session.request_data, {'path': "/a/path"})

        # returns empty info if there is no data for the event stream
        self.session.response_data = {'data_info': None}
        info_returned = await self.node.event_stream_info("/a/path")
        self.assertEqual(info_returned.start, None)
        self.assertEqual(info_returned.end, None)
        self.assertEqual(info_returned.event_count, 0)
        self.assertEqual(info_returned.total_time, 0)
        self.assertEqual(info_returned.bytes, 0)

    async def test_gets_event_stream(self):
        src = EventStream(name="test")
        src.id = 10
        self.session.response_data = src.to_json()

        # gets the stream by stream object
        src_returned = await self.node.event_stream_get(src)
        self.assertEqual(self.session.method, 'GET')
        self.assertEqual(self.session.path, "/event.json")
        self.assertEqual(self.session.request_data, {'id': 10})
        self.assertEqual(src.name, src_returned.name)
        self.assertEqual(src.id, src_returned.id)

        # gets the stream by id
        await self.node.event_stream_get(20)
        self.assertEqual(self.session.request_data, {'id': 20})

        # gets the stream by path
        await self.node.event_stream_get("/a/path")
        self.assertEqual(self.session.request_data, {'path': "/a/path"})

    async def test_creates_event_stream_on_get(self):
        new_stream = EventStream(name="exist")
        new_stream.id = 99
        self.session.response_data = [ApiError("error"), new_stream.to_json()]
        self.session.multiple_calls = True
        src_returned = await self.node.event_stream_get("/does/not/exist", create=True)
        # tries and fails to retrieve the stream
        self.assertEqual(self.session.methods[0], 'GET')
        self.assertEqual(self.session.paths[0], "/event.json")
        self.assertEqual(self.session.request_data[0], {'path': "/does/not/exist"})
        # submits another request to create it
        self.assertEqual(self.session.methods[1], 'POST')
        self.assertEqual(self.session.paths[1], "/event.json")
        new_stream.id = None
        self.assertEqual(self.session.request_data[1], {'stream': new_stream.to_json(),
                                                        'dest_path': "/does/not"})
        self.assertEqual(src_returned.name, "exist")
        self.assertEqual(src_returned.id, 99)

    async def tests_validates_event_fields(self):
        # valid fields, no exception raised
        EventStream(name="test",
                    event_fields = {'field1': 'string', 'field2': 'numeric', 'field3': 'category:["cat1","cat2"]'})
        

        # invalid fields
        with self.assertRaises(errors.ConfigurationError):
            event_fields = {'field1': 'string', 'field2': 'numeric', 'field3': 'category:[]', 'field4': 'bad'}
            EventStream(name="test",event_fields=event_fields)
        with self.assertRaises(errors.ConfigurationError):
            event_fields = {'field1': 'string', 'field2': 'numeric', 'field3': 'category:bad'}
            EventStream(name="test",event_fields=event_fields)
        with self.assertRaises(errors.ConfigurationError):
            event_fields = {'field1': 'string', 'field2': 'numeric', 'field3': 'bad'}
            EventStream(name="test",event_fields=event_fields)

    async def test_updates_event_stream(self):
        src = EventStream(name="test")
        src.id = 100

        # updates the event stream by object
        await self.node.event_stream_update(src)
        self.assertEqual(self.session.method, 'PUT')
        self.assertEqual(self.session.path, "/event.json")
        self.assertEqual(self.session.request_data, {'id': src.id, 'stream': src.to_json()})

        # updating with invalid fields raises an error
        src.event_fields = {'field1': 'bad', 'field2': 'numeric'}
        with self.assertRaises(errors.ConfigurationError):
            await self.node.event_stream_update(src)

    async def test_moves_event_stream(self):
        src = EventStream(name="test")
        src.id = 100
        folder = Folder(name="test")
        folder.id = 1
        await self.node.event_stream_move(src, folder)
        self.assertEqual(self.session.method, 'PUT')
        self.assertEqual(self.session.path, "/event/move.json")
        self.assertEqual(self.session.request_data, {'src_id': src.id,
                                                     'dest_id': 1})
        # can move by ID
        await self.node.event_stream_move(10, 100)
        self.assertEqual(self.session.request_data, {'src_id': 10,
                                                     'dest_id': 100})
        # can move by path
        await self.node.event_stream_move("/a/path", "/another/path")
        self.assertEqual(self.session.request_data, {'src_path': "/a/path",
                                                     'dest_path': "/another/path"})

    async def test_writes_events_to_stream(self):
        events = [Event(start_time=i, end_time=i + 1, content={'data': 'value'})
                  for i in range(800)]
        events_returned = [{'id': i, 'start_time': i, 'end_time': i + 1, 'content': {'data': 'value'}}
                           for i in range(800)]
        self.session.response_data = [{'events': events_returned[:500]},
                                      {'events': events_returned[500:]}]
        self.session.multiple_calls = True
        await self.node.event_stream_write("/a/path", events)
        self.assertEqual(self.session.methods, ['POST', 'POST'])
        self.assertEqual(self.session.paths, ['/event/data.json', '/event/data.json'])
        self.assertEqual(self.session.request_data[0]['path'], "/a/path")
        self.assertEqual(len(self.session.request_data[0]['events']), 500)
        self.assertEqual(len(self.session.request_data[1]['events']), len(events[500:]))

        print("TODO!!")
        # make sure events now have ids
        #for i in range(len(events)):
        #    self.assertEqual(events[i].id, i)
