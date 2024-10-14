from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web
from sqlalchemy.orm import Session
import asyncio
from joule.models import folder, DataStream, Folder, Element, StreamInfo, EventStream
from joule.api.event_stream import EventStream as ApiEventStream
import joule.controllers
from tests.controllers.helpers import create_db, MockStore, MockEventStore
from joule import app_keys
from joule.constants import EndPoints
import testing.postgresql
psql_key = web.AppKey("psql", testing.postgresql.Postgresql)

class TestFolderController(AioHTTPTestCase):

    async def tearDownAsync(self):
        self.app[app_keys.db].close()
        self.app[psql_key].stop()
        await self.client.close()

    async def get_application(self):
        app = web.Application()
        app.add_routes(joule.controllers.routes)
        # this takes a while, adjust the expected coroutine execution time
        loop = asyncio.get_running_loop()
        loop.slow_callback_duration = 2.0
        # create two event streams to try recursive dele\ operations
        stream1 = ApiEventStream(name="test",description="test stream",keep_us=10e6, 
                            event_fields={"field1": "string",
                                        "field2": 'category:["1","2","3"]'})
        stream2 = ApiEventStream(name="test2",description="test stream2",keep_us=10e6,
                            event_fields={"field1": "string",
                                        "field2": 'category:["1","2","3"]'})
        # place the events under /top/leaf to test delete operations
        app[app_keys.db], app[psql_key] = create_db([
            "/other/middle/stream3:int16[val1, val2]",
            "/top/leaf/stream1:float32[x, y, z]",
            "/top/middle/leaf/stream2:int16[val1, val2]"],
            [stream1,stream2],"/top/leaf")
        app[app_keys.data_store] = MockStore()
        app[app_keys.event_store] = MockEventStore()
        return app

    async def test_stream_list(self):
        db: Session = self.app[app_keys.db]
        my_stream: DataStream = db.query(DataStream).filter_by(name="stream1").one()
        store: MockStore = self.app[app_keys.data_store]
        mock_info = StreamInfo(start=0, end=100, rows=200)
        store.set_info(my_stream, mock_info)

        resp = await self.client.request("GET", EndPoints.folders)
        actual = await resp.json()
        # list of active streams should be in the response
        self.assertTrue("active_data_streams" in actual)
        # remove active_streams from the response, so we can compare it with the database copy
        del actual['active_data_streams']
        # basic check to see if JSON response matches database structure
        expected = folder.root(db).to_json()
        self.assertEqual(actual, expected)
        # test to see if data-info flag works
        resp = await self.client.request("GET", EndPoints.folders, params={"data-info": ""})
        actual = await resp.json()
        expected = folder.root(db).to_json(data_stream_info={my_stream.id: mock_info})
        # remove active_streams from the response, so we can compare it with the database copy
        del actual['active_data_streams']
        self.assertEqual(actual, expected)


    async def test_folder_info(self):
        # query by path
        params = {
            "path": "/top/leaf"
        }
        resp = await self.client.get(EndPoints.folder, params=params)
        self.assertEqual(resp.status, 200)
        json = await resp.json()
        self.assertEqual(json["name"], "leaf")
        self.assertEqual(len(json["streams"]), 1)
        folder_id = json["id"]
        # query by id
        resp = await self.client.get(EndPoints.folder, params={"id": folder_id})
        self.assertEqual(resp.status, 200)
        json = await resp.json()
        self.assertEqual(json["name"], "leaf")
        self.assertEqual(len(json["streams"]), 1)


    async def test_folder_move_by_path(self):
        db: Session = self.app[app_keys.db]
        # move stream1 into folder3
        payload = {
            "src_path": "/top/leaf",
            "dest_path": "/other"
        }
        source_parent_created_at = folder.find("/top", db).updated_at
        dest_parent_created_at = folder.find("/other", db).updated_at
        other_folder_created_at = folder.find("/other/middle", db).updated_at
        resp = await self.client.put(EndPoints.folder_move, json=payload)
        self.assertEqual(resp.status, 200)
        f = folder.find("/other/leaf", db)
        self.assertEqual(f.data_streams[0].name, "stream1")
        self.assertIsNone(folder.find("/top/leaf", db))
        # make sure the parent timestamps are updated
        self.assertGreater(folder.find("/top", db).updated_at, source_parent_created_at)
        self.assertGreater(folder.find("/other", db).updated_at, dest_parent_created_at)
        # other timestamps should not be updated
        self.assertEqual(folder.find("/other/middle", db).updated_at, other_folder_created_at)

    async def test_folder_move_by_id(self):
        db: Session = self.app[app_keys.db]
        # move stream1 into folder3
        dest_folder = folder.find("/top/middle/leaf", db)
        src_folder = folder.find("/top/leaf", db)
        payload = {
            "src_id": src_folder.id,
            "dest_id": dest_folder.id
        }
        resp = await self.client.put(EndPoints.folder_move, json=payload)
        self.assertEqual(resp.status, 200)
        self.assertEqual(src_folder.id,
                         folder.find("/top/middle/leaf/leaf", db).id)
        self.assertIsNone(folder.find("/top/leaf", db))


    async def test_folder_delete_by_path(self):
        db: Session = self.app[app_keys.db]
        folder.find("/top/leaf", db)
        payload = {'path': "/top/leaf"}
        # there are 2 event streams associated with this folder
        self.assertEqual(2, db.query(EventStream).count())
        resp = await self.client.delete(EndPoints.folder, params=payload)
        self.assertEqual(resp.status, 200)

        self.assertIsNone(folder.find("/top/leaf", db))
        # deletes the streams
        self.assertIsNone(folder.find_stream_by_path("/top/leaf/stream1", db))
        # deletes the event streams
        self.assertIsNone(folder.find_stream_by_path("/top/leaf/test", db))
        self.assertEqual(0, db.query(EventStream).count())
        # keeps the parent folders
        self.assertIsNotNone(folder.find("/top", db))


    async def test_folder_delete_by_id(self):
        db: Session = self.app[app_keys.db]
        f_count = db.query(Folder).count()
        f = folder.find("/an/empty/folder", db, create=True)
        parent_updated_at = f.parent.updated_at
        top_parent_updated_at = f.parent.parent.updated_at
        self.assertEqual(db.query(Folder).count(), f_count + 3)
        payload = {'id': f.id}
        resp = await self.client.delete(EndPoints.folder, params=payload)
        self.assertEqual(resp.status, 200)

        self.assertIsNone(folder.find("/an/empty/folder", db))
        # keeps the parent folders
        self.assertEqual(f_count + 2, db.query(Folder).count())
        self.assertIsNotNone(folder.find("/an/empty", db))
        # parent folders should have updated timestamps
        self.assertGreater(f.parent.updated_at, parent_updated_at)
        self.assertGreater(f.parent.parent.updated_at, top_parent_updated_at)

    async def test_folder_recursive_delete(self):
        db: Session = self.app[app_keys.db]
        f = folder.find("/top", db)
        payload = {'path': "/top", 'recursive': "1"}
        resp = await self.client.delete(EndPoints.folder, params=payload)
        self.assertEqual(resp.status, 200)
        # this is the top folder so everything under it should be gone
        # there are three other folders: /, /other, and /other/middle
        self.assertEqual(3, db.query(Folder).count())
        # there is one other stream: /other/middle/stream3:int16[val1, val2]
        self.assertEqual(1, db.query(DataStream).count())
        self.assertEqual(2, db.query(Element).count())
        # the event streams are gone
        self.assertEqual(0, db.query(EventStream).count())

    async def test_folder_update(self):
        db: Session = self.app[app_keys.db]
        my_folder = folder.find("/top/middle/leaf", db)
        other_folder = folder.find("/top/other", db, create=True)
        created_at = my_folder.updated_at
        middle_parent_created_at = my_folder.parent.updated_at
        top_parent_created_at = my_folder.parent.parent.updated_at
        other_folder_created_at = other_folder.updated_at
        # change the stream name
        payload = {
            "id": my_folder.id,
            "folder": {"name": "new name", "description": "new description"}
        }
        resp = await self.client.put(EndPoints.folder, json=payload)
        self.assertEqual(200, resp.status)
        my_folder: DataStream = db.get(Folder,my_folder.id)
        self.assertEqual("new name", my_folder.name)
        self.assertEqual("new description", my_folder.description)
        # make sure updated timestamps are more recent than created timestamps
        self.assertGreater(my_folder.updated_at, created_at)
        self.assertGreater(my_folder.parent.updated_at, middle_parent_created_at)
        self.assertGreater(my_folder.parent.parent.updated_at, top_parent_created_at)
        # make sure other folder is not updated
        self.assertEqual(other_folder_created_at, other_folder.updated_at)
        # make sure the JSON response is correct
        json = await resp.json()
        self.assertEqual("new name", json["name"])
        self.assertEqual(my_folder.updated_at.isoformat(), json["updated_at"])
