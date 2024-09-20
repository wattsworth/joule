from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web
import aiohttp
import json
import numpy as np
from sqlalchemy.orm import Session
import asyncio
from joule.models import DataStream, pipes
import joule.controllers
from joule.models import Folder, EventStream
from joule.models.folder import find as find_folder
from tests.controllers.helpers import create_db, MockSupervisor, MockEventStore
from joule.api.event_stream import EventStream as ApiEventStream, from_json as event_stream_from_json
from joule.api.event import Event, from_json as event_from_json
from tests import helpers
from joule import app_keys
from joule.constants import EndPoints

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
    
        app[app_keys.db], app[psql_key] = await asyncio.to_thread(lambda: create_db(["/other/folder/stub_stream:float32[x,y,z]"],[stream1]))
        self.test_stream_id = app[app_keys.db].query(EventStream).filter_by(name="test").one().id
        self.test_stream = stream1 # stream2 is to test for name collisions
        self.test_stream.id = self.test_stream_id # set the id to match the database
        app[app_keys.event_store] = MockEventStore()
        self.supervisor = MockSupervisor()
        app[app_keys.supervisor] = self.supervisor
        return app
    
    async def test_update_event_stream(self):
        db = self.app[app_keys.db]
        stream = db.query(EventStream).filter_by(id=self.test_stream_id).one()
        prev_update = stream.updated_at
        self.test_stream.name = "new_name"
        self.test_stream.description = "new description"
        self.test_stream.keep_us = 20e6
        self.test_stream.event_fields = {"new_field": "string"}
        resp: aiohttp.ClientResponse = await \
            self.client.put(EndPoints.event, json={"id": self.test_stream_id, "stream": self.test_stream.to_json()})
        # print the response text if the test fails
        if resp.status != 200:
            print(await resp.text())
        self.assertEqual(resp.status, 200)
        # returns the stream as JSON
        data = await resp.json()
        stream = event_stream_from_json(data)
        self.assertEqual(stream.name, "new_name")
        # database is updated
        stream = db.query(EventStream).filter_by(id=self.test_stream_id).one()
        self.assertEqual(stream.name, "new_name")
        self.assertEqual(stream.description, "new description")
        self.assertEqual(stream.keep_us, 20e6)
        self.assertEqual(stream.event_fields, {"new_field": "string"})
        # updated_at is more recent 
        self.assertGreater(stream.updated_at, prev_update)

    async def test_create_event_streams(self):
        store: MockEventStore = self.app[app_keys.event_store]
        new_stream = ApiEventStream(name="test",description="test stream",keep_us=10e6, 
                                 event_fields={"field1": "string",
                                               "field2": 'category:["1","2","3"]'})
        resp: aiohttp.ClientResponse = await \
            self.client.post(EndPoints.event, json={"dest_path": "/folder1", "stream": new_stream.to_json()})
        self.assertEqual(resp.status, 200)
        self.assertTrue(store.create_called)
        self.assertEqual(store.new_stream.folder.name,'folder1')
        self.assertEqual(store.new_stream.name,'test')
        self.assertEqual(store.new_stream.description,'test stream')
        self.assertEqual(store.new_stream.keep_us,10e6)
        self.assertEqual(store.new_stream.event_fields['field2'], 'category:["1","2","3"]')

        # can also create a stream with a destination id
        dest_id = self.app[app_keys.db].query(Folder).filter_by(name="folder1").one().id
        new_stream.name="test2"
        store.create_called = False
        resp: aiohttp.ClientResponse = await \
            self.client.post(EndPoints.event, json={"dest_id": dest_id, "stream": new_stream.to_json()})
        self.assertEqual(resp.status, 200)
        self.assertTrue(store.create_called)
        self.assertEqual(store.new_stream.folder.name,'folder1')
        self.assertEqual(store.new_stream.name,'test2')
    
        # names must be unique within a folder
        store.create_called = False
        resp: aiohttp.ClientResponse = await \
            self.client.post(EndPoints.event, json={"dest_id": dest_id, "stream": new_stream.to_json()})
        self.assertEqual(resp.status, 400)
        self.assertFalse(store.create_called)
        msg = await resp.text()
        self.assertIn('same name', msg)

    async def test_destroy_event_stream_by_path(self):
        self.assertEqual(self.app[app_keys.db].query(EventStream).filter_by(id=self.test_stream_id).count(), 1)
        prev_update = self.app[app_keys.db].query(Folder).filter_by(name="events").one().updated_at
        resp: aiohttp.ClientResponse = await \
            self.client.delete(EndPoints.event, params={"path": "/events/test"})
        self.assertEqual(resp.status, 200)
        self.assertEqual(self.app[app_keys.db].query(EventStream).filter_by(id=self.test_stream_id).count(), 0)
        # make sure the parent folder timestamp is updated
        updated_at = self.app[app_keys.db].query(Folder).filter_by(name="events").one().updated_at
        self.assertGreater(updated_at, prev_update)
    
    async def test_destroy_event_stream_by_id(self):
        self.assertEqual(self.app[app_keys.db].query(EventStream).filter_by(id=self.test_stream_id).count(), 1)
        prev_update = self.app[app_keys.db].query(Folder).filter_by(name="events").one().updated_at
        resp: aiohttp.ClientResponse = await \
            self.client.delete(EndPoints.event, params={"id": self.test_stream_id})
        self.assertEqual(resp.status, 200)
        self.assertEqual(self.app[app_keys.db].query(EventStream).filter_by(id=self.test_stream_id).count(), 0)
        # make sure the parent folder timestamp is updated
        updated_at = self.app[app_keys.db].query(Folder).filter_by(name="events").one().updated_at
        self.assertGreater(updated_at, prev_update)
    
    async def test_get_event_stream(self):
        resp: aiohttp.ClientResponse = await \
            self.client.get(EndPoints.event, params={"id": 1})
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        stream = event_stream_from_json(data)
        self.assertEqual(stream.name, "test")

        resp: aiohttp.ClientResponse = await \
            self.client.get(EndPoints.event, params={"path": "/events/test"})
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        stream = event_stream_from_json(data)
        self.assertEqual(stream.name, "test")

    async def test_move_event_stream(self):
        orig_parent = find_folder("/events", self.app[app_keys.db])
        expected_new_parent = find_folder("/other/folder", self.app[app_keys.db])
        new_parent_orig_ts = expected_new_parent.updated_at
        old_parent_orig_ts = find_folder("/events", self.app[app_keys.db]).updated_at

        resp: aiohttp.ClientResponse = await \
            self.client.put(EndPoints.event_move, json={"dest_path": "/other/folder", "src_path": "/events/test"})
        self.assertEqual(resp.status, 200)
        event_stream = event_stream_from_json((await resp.json())['stream'])
        # returns the stream
        self.assertEqual(event_stream.name, "test")
        # stream is moved, make sure the event stream's folder id matches the new parent
        actual_parent_id = self.app[app_keys.db].query(EventStream).filter_by(name="test").one().folder_id
        self.assertEqual(actual_parent_id, expected_new_parent.id)
        # make sure the parent folder timestamps are updated
        new_parent_updated_ts = find_folder("/other/folder", self.app[app_keys.db]).updated_at
        self.assertGreater(new_parent_updated_ts, new_parent_orig_ts)
        old_parent_updated_ts = find_folder("/events", self.app[app_keys.db]).updated_at
        self.assertGreater(old_parent_updated_ts, old_parent_orig_ts)

        # also works with ids, move it back to the original location
        resp: aiohttp.ClientResponse = await \
            self.client.put(EndPoints.event_move, json={"dest_id": orig_parent.id, 
                                                        "src_id": self.test_stream_id})
        self.assertEqual(resp.status, 200)
        actual_parent_id = self.app[app_keys.db].query(EventStream).filter_by(name="test").one().folder_id
        self.assertEqual(actual_parent_id, orig_parent.id)

    async def test_write_events(self):
        event_store = self.app[app_keys.event_store]
        ### writes events given an event stream id
        events = [Event(start_time=i,end_time=i+1000,content={"field1": i}, 
                        event_stream_id=self.test_stream.id, id=i) for i in range(0,10000,1000)]
        resp: aiohttp.ClientResponse = await \
            self.client.post(EndPoints.event_data, json={"id": self.test_stream_id, "events": [e.to_json() for e in events]})
        self.assertEqual(resp.status, 200)
        # make sure the events are written to the event store
        self.assertTrue(event_store.upsert_called)
        self.assertEqual(event_store.upserted_events, [e.to_json() for e in events])
        event_store.reset()

        ### writes events given an event stream path
        resp: aiohttp.ClientResponse = await \
            self.client.post(EndPoints.event_data, json={"path": "/events/test", "events": [e.to_json() for e in events]})
        self.assertEqual(resp.status, 200)
        # make sure the events are written to the event store
        self.assertTrue(event_store.upsert_called)
        self.assertEqual(event_store.upserted_events, [e.to_json() for e in events])
        # the correct event_stream_id is used
        self.assertEqual(event_store.upserted_events[0]['event_stream_id'], self.test_stream_id)
        event_store.reset()

        ### resets ID field when events do not have the right event_stream_id
        events[0].event_stream_id = 999
        resp: aiohttp.ClientResponse = await \
            self.client.post(EndPoints.event_data, json={"id": self.test_stream_id, "events": [e.to_json() for e in events]})
        self.assertEqual(resp.status, 200)
        # make sure the events are written to the event store
        self.assertTrue(event_store.upsert_called)
        modified_event = event_store.upserted_events[0]
        self.assertIsNone(modified_event['id']) # ID is removed so it will be treated as a new event
        self.assertEqual(modified_event['event_stream_id'], self.test_stream_id) # event_stream_id is corrected
        # the rest of the events are unchanged
        self.assertEqual(event_store.upserted_events[1:], [e.to_json() for e in events[1:]])

    async def test_event_stream_count_events(self):
        event_store = self.app[app_keys.event_store]

        ### Works with default parameters
        resp = await self.client.get(EndPoints.event_data_count, 
                                     params={"id": self.test_stream_id})
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        self.assertEqual(data['count'], 10) # from MockEventStore
        # make sure the event store is queried
        self.assertTrue(event_store.count_called)
        # default parameters passed to count
        target_stream, start, end, json_filter, include_on_going_events = event_store.count_params
        self.assertTupleEqual((start, end, json_filter, include_on_going_events), (None, None, None, False))
        self.assertEqual(target_stream.id, self.test_stream_id)
        event_store.reset()

        ### Can specify optional parameters
        json_filter = '[[["id","=","3"]]]'
        start = 0
        end = 100
        include_on_going_events = True
        resp = await self.client.get(EndPoints.event_data_count, 
                                     params={"id": self.test_stream_id,
                                             "start": start,
                                             "end": end,
                                             "filter": json.dumps(json_filter),
                                             "include_on_going_events": 0})
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        self.assertEqual(data['count'], 10)
        self.assertTrue(event_store.count_called)
        # optional parameters are correctly parsed
        self.assertEqual(event_store.count_params[0].id, self.test_stream.id)
        self.assertEqual(event_store.count_params[1], start)
        self.assertEqual(event_store.count_params[2], end)
        self.assertEqual(event_store.count_params[3], json_filter)
        self.assertFalse(event_store.count_params[4])
        event_store.reset()

        ### Can find by path
        resp = await self.client.get(EndPoints.event_data_count, 
                                     params={"path": "/events/test"})
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        self.assertEqual(data['count'], 10)
        self.assertTrue(event_store.count_called)
        self.assertEqual(event_store.count_params[0].id, self.test_stream.id)