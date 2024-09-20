from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web
import aiohttp
import numpy as np
from sqlalchemy.orm import Session
import asyncio
from joule.models import EventStream, Folder
import joule.controllers
from tests.controllers.helpers import create_db, MockSupervisor, MockEventStore
from joule.api.event_stream import EventStream as ApiEventStream
from joule.models.folder import find as find_folder
from joule.api.event import Event
from tests import helpers
from joule import app_keys
from joule.constants import EndPoints, ApiErrorMessages

import testing.postgresql
psql_key = web.AppKey("psql", testing.postgresql.Postgresql)

class TestEventController(AioHTTPTestCase):

    async def tearDownAsync(self):
        self.app[app_keys.db].close()
        await asyncio.to_thread(self.app[psql_key].stop)
        await self.client.close()

    async def get_application(self):
        app = web.Application()
        app.add_routes(joule.controllers.routes)
        stream1 = ApiEventStream(name="test",description="test stream",keep_us=10e6, 
                              event_fields={"field1": "string",
                                           "field2": 'category:["1","2","3"]'})
        stream2 = ApiEventStream(name="test2",description="test stream",keep_us=10e6, 
                              event_fields={"field1": "string",
                                           "field2": 'category:["1","2","3"]'})
        app[app_keys.db], app[psql_key] = await asyncio.to_thread(lambda: create_db([],[stream1, stream2]))
        self.test_stream_id = app[app_keys.db].query(EventStream).filter_by(name="test").one().id
        self.test_stream = stream1 # stream2 is to test for name collisions
        self.test_stream.id = self.test_stream_id # set the id to match the database
        app[app_keys.event_store] = MockEventStore()
        self.supervisor = MockSupervisor()
        app[app_keys.supervisor] = self.supervisor
        return app
    
    async def test_create_event_stream_errors(self):
        store: MockEventStore = self.app[app_keys.event_store]
        new_stream = ApiEventStream(name="test",description="test stream",keep_us=10e6, 
                                 event_fields={"field1": "string",
                                               "field2": 'category:["1","2","3"]'})
        ### must send JSON data
        resp: aiohttp.ClientResponse = await \
            self.client.post(EndPoints.event, params={"dest_path": "/folder1", "stream": "not json"})
        self.assertEqual(resp.status, 400)
        msg = await resp.text()
        self.assertIn('content-type', msg)
        self.assertFalse(store.create_called)

        ### must send dest_path
        resp: aiohttp.ClientResponse = await \
            self.client.post(EndPoints.event, json={"stream": new_stream.to_json()})
        self.assertEqual(resp.status, 400)
        msg = await resp.text()
        self.assertIn('destination', msg)
        self.assertFalse(store.create_called)

        ### must send stream
        resp: aiohttp.ClientResponse = await \
            self.client.post(EndPoints.event, json={"dest_path": "/folder1"})
        self.assertEqual(resp.status, 400)
        msg = await resp.text()
        self.assertIn('stream', msg)
        self.assertFalse(store.create_called)

        ### destination must be valid (missing a /)
        resp: aiohttp.ClientResponse = await \
            self.client.post(EndPoints.event, json={"dest_path": "folder1", "stream": new_stream.to_json()})
        self.assertEqual(resp.status, 400)
        msg = await resp.text()
        self.assertIn('invalid path', msg)
        self.assertFalse(store.create_called)

        ### stream JSON must be valid
        resp: aiohttp.ClientResponse = await \
            self.client.post(EndPoints.event, json={"dest_path": "/folder1", "stream": "Not JSON :("})
        self.assertEqual(resp.status, 400)
        msg = await resp.text()
        self.assertIn('JSON', msg)
        self.assertFalse(store.create_called)

        ### stream JSON must have all the correct fields
        stream_json = new_stream.to_json()
        stream_json.pop('name')
        resp: aiohttp.ClientResponse = await \
            self.client.post(EndPoints.event, json={"dest_path": "/folder1", "stream": stream_json})
        self.assertEqual(resp.status, 400)
        msg = await resp.text()
        self.assertIn('missing stream attribute', msg)
        self.assertFalse(store.create_called)

    async def test_delete_event_stream_errors(self):
        ### must send path or id
        prev_update = self.app[app_keys.db].query(Folder).filter_by(name="events").one().updated_at
        resp: aiohttp.ClientResponse = await \
            self.client.delete(EndPoints.event, params={})
        self.assertEqual(resp.status, 400)
        msg = await resp.text()
        self.assertIn('path', msg)
        # make sure the parent folder timestamp is not updated
        updated_at = self.app[app_keys.db].query(Folder).filter_by(name="events").one().updated_at
        self.assertEqual(updated_at, prev_update)

        ## path must exist
        resp: aiohttp.ClientResponse = await \
            self.client.delete(EndPoints.event, params={"path": "/does/not/exist"})
        self.assertEqual(resp.status, 404)
        msg = await resp.text()
        self.assertIn('does not exist', msg)
        # make sure the parent folder timestamp is not updated
        updated_at = self.app[app_keys.db].query(Folder).filter_by(name="events").one().updated_at
        self.assertEqual(updated_at, prev_update)
    
    async def test_get_event_stream_info_errors(self):
        ### must send id
        resp: aiohttp.ClientResponse = await \
            self.client.get(EndPoints.event, params={})
        self.assertEqual(resp.status, 400)
        msg = await resp.text()
        self.assertIn('id', msg)

        ### id must exist
        resp: aiohttp.ClientResponse = await \
            self.client.get(EndPoints.event, params={"id": 999})
        self.assertEqual(resp.status, 404)
        msg = await resp.text()
        self.assertIn('does not exist', msg)

    async def test_move_event_stream_errors(self):
        ### must send id
        resp: aiohttp.ClientResponse = await \
            self.client.put(EndPoints.event_move, json={})
        self.assertEqual(resp.status, 400)
        msg = await resp.text()
        self.assertIn('id', msg)

        ### id must exist
        resp: aiohttp.ClientResponse = await \
            self.client.put(EndPoints.event_move, json={"src_id": 999})
        self.assertEqual(resp.status, 404)
        msg = await resp.text()
        self.assertIn('does not exist', msg)

        ### must send dest_path
        resp: aiohttp.ClientResponse = await \
            self.client.put(EndPoints.event_move, json={"src_id": 1})
        self.assertEqual(resp.status, 400)
        msg = await resp.text()
        self.assertIn('destination', msg)

        ### dest_path must be valid
        resp: aiohttp.ClientResponse = await \
            self.client.put(EndPoints.event_move, json={"src_id": 1, "dest_path": "not/valid"})
        self.assertEqual(resp.status, 400)
        
        ### name must be unique in destination
        duplicate_stream = ApiEventStream(name="test",description="test stream")
        resp: aiohttp.ClientResponse = await \
            self.client.post(EndPoints.event, json={"dest_path": "/other/folder", "stream": duplicate_stream.to_json()})
        self.assertEqual(resp.status, 200)
        resp: aiohttp.ClientResponse = await \
            self.client.put(EndPoints.event_move, json={"src_path": "/events/test", "dest_path": "/other/folder"})
        self.assertEqual(resp.status, 400)
        msg = await resp.text()
        self.assertIn('same name', msg)
        # make sure the stream didn't move, the parent_id should be the same
        actual_parent_id = self.app[app_keys.db].query(EventStream).filter_by(id=self.test_stream_id).one().folder_id
        self.assertEqual(actual_parent_id, find_folder("/events", self.app[app_keys.db]).id)

    async def test_event_stream_update_errors(self):
        db = self.app[app_keys.db]
        stream = db.query(EventStream).filter_by(id=self.test_stream_id).one()
        prev_update = stream.updated_at
        
        ### must send JSON data for stream
        resp: aiohttp.ClientResponse = await \
            self.client.put(EndPoints.event, json={"id": self.test_stream_id})
        self.assertEqual(resp.status, 400)
        # database is not updated
        stream = db.query(EventStream).filter_by(id=self.test_stream_id).one()
        self.assertEqual(stream.updated_at, prev_update)
        
        ### must send id
        resp: aiohttp.ClientResponse = await \
            self.client.put(EndPoints.event, json={"stream": self.test_stream.to_json()})
        self.assertEqual(resp.status, 400)
        # database is not updated
        stream = db.query(EventStream).filter_by(id=self.test_stream_id).one()
        self.assertEqual(stream.updated_at, prev_update)

        ### id must be valid
        resp: aiohttp.ClientResponse = await \
            self.client.put(EndPoints.event, json={"id":999, "stream": self.test_stream.to_json()})
        self.assertEqual(resp.status, 404)
        # database is not updated
        stream = db.query(EventStream).filter_by(id=self.test_stream_id).one()
        self.assertEqual(stream.updated_at, prev_update)

        ### stream JSON must be valid
        resp: aiohttp.ClientResponse = await \
            self.client.put(EndPoints.event, json={"id": self.test_stream_id, "stream": "not json"})
        self.assertEqual(resp.status, 400)
        # database is not updated
        stream = db.query(EventStream).filter_by(id=self.test_stream_id).one()
        self.assertEqual(stream.updated_at, prev_update)

        ### name must be unique in the folder
        self.test_stream.name="test2" # conflict
        resp: aiohttp.ClientResponse = await \
            self.client.put(EndPoints.event, json={"id":self.test_stream_id, "stream": self.test_stream.to_json()})
        self.assertEqual(resp.status, 400)
        msg = await resp.text()
        self.assertIn('same name', msg)

    async def test_event_stream_write_errors(self):
        event_store = self.app[app_keys.event_store]
        ### must specify an id or path
        events = [Event(start_time=i,end_time=i+1000,content={"field1": i}, 
                        event_stream_id=self.test_stream.id, id=i) for i in range(0,10000,1000)]
        resp: aiohttp.ClientResponse = await \
            self.client.post(EndPoints.event_data, json={"events": [e.to_json() for e in events]})
        self.assertEqual(resp.status, 400)
        self.assertFalse(event_store.upsert_called)
        msg = await resp.text()
        self.assertIn(ApiErrorMessages.specify_id_or_path, msg)

        ### stream must exist (valid path)
        resp: aiohttp.ClientResponse = await \
            self.client.post(EndPoints.event_data, json={"events": [e.to_json() for e in events], "path": "/does/not/exist"})
        self.assertEqual(resp.status, 404)
        self.assertFalse(event_store.upsert_called)
        msg = await resp.text()
        self.assertIn(ApiErrorMessages.stream_does_not_exist, msg)

        ### must send events
        resp: aiohttp.ClientResponse = await \
            self.client.post(EndPoints.event_data, json={"path": "/events/test"})
        self.assertEqual(resp.status, 400)
        self.assertFalse(event_store.upsert_called)
        msg = await resp.text()
        self.assertIn('events', msg)

        ### events must have an event_stream_id
        events_json = [e.to_json() for e in events]
        events_json[0].pop('event_stream_id')
        resp: aiohttp.ClientResponse = await \
            self.client.post(EndPoints.event_data, json={"events": events_json, "path": "/events/test"})
        self.assertEqual(resp.status, 400)
        self.assertFalse(event_store.upsert_called)
        msg = await resp.text()
        self.assertIn('event_stream_id', msg)

    async def test_aevent_stream_count_errors(self):
        event_store = self.app[app_keys.event_store]
        ### must specify an id or path
        resp: aiohttp.ClientResponse = await \
            self.client.get(EndPoints.event_data_count, params={"start": 0, "end": 10000})
        self.assertEqual(resp.status, 400)
        self.assertFalse(event_store.count_called)
        msg = await resp.text()
        self.assertIn(ApiErrorMessages.specify_id_or_path, msg)

        ### stream must exist (valid path)
        resp: aiohttp.ClientResponse = await \
            self.client.get(EndPoints.event_data_count, params={"path": "/does/not/exist"})
        self.assertEqual(resp.status, 404)
        self.assertFalse(event_store.count_called)
        msg = await resp.text()
        self.assertIn(ApiErrorMessages.stream_does_not_exist, msg)

        ### parameters must have valid datatype (int)
        resp: aiohttp.ClientResponse = await \
            self.client.get(EndPoints.event_data_count, params={"path": "/events/test", "start": "not an int", "end": 10000})
        self.assertEqual(resp.status, 400)
        self.assertFalse(event_store.count_called)
        msg = await resp.text()
        self.assertIn(ApiErrorMessages.f_parameter_must_be_an_int.format(parameter='start'), msg)

        ### start must be before end
        resp: aiohttp.ClientResponse = await \
            self.client.get(EndPoints.event_data_count, params={"path": "/events/test", "start": 10000, "end": 0})
        self.assertEqual(resp.status, 400)
        self.assertFalse(event_store.count_called)
        msg = await resp.text()
        self.assertIn(ApiErrorMessages.start_must_be_before_end, msg)

        ### invalid filter parameter
        resp: aiohttp.ClientResponse = await \
            self.client.get(EndPoints.event_data_count, params={"path": "/events/test", "start": 0, "end": 10000, "filter": "not valid"})   
        self.assertEqual(resp.status, 400)
        self.assertFalse(event_store.count_called)
        msg = await resp.text()
        self.assertIn(ApiErrorMessages.invalid_filter_parameter, msg)
