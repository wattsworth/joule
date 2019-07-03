from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web
from sqlalchemy.orm import Session

from joule.models import folder, Stream, Folder, Element
import joule.controllers
from tests.controllers.helpers import create_db, MockStore


class TestFolderController(AioHTTPTestCase):

    async def tearDownAsync(self):
        self.app["db"].close()
        self.app["psql"].stop()

    async def get_application(self):
        app = web.Application()
        app.add_routes(joule.controllers.routes)
        app["db"], app["psql"] = create_db(["/top/leaf/stream1:float32[x, y, z]",
                                            "/top/middle/leaf/stream2:int8[val1, val2]"])
        app["data-store"] = MockStore()
        return app

    @unittest_run_loop
    async def test_folder_info(self):
        # query by path
        params = {
            "path": "/top/leaf"
        }
        resp = await self.client.get("/folder.json", params=params)
        self.assertEqual(resp.status, 200)
        json = await resp.json()
        self.assertEqual(json["name"], "leaf")
        self.assertEqual(len(json["streams"]), 1)
        folder_id = json["id"]
        # query by id
        resp = await self.client.get("/folder.json", params={"id": folder_id})
        self.assertEqual(resp.status, 200)
        json = await resp.json()
        self.assertEqual(json["name"], "leaf")
        self.assertEqual(len(json["streams"]), 1)

    @unittest_run_loop
    async def test_folder_move_by_path(self):
        db: Session = self.app["db"]
        # move stream1 into folder3
        payload = {
            "src_path": "/top/leaf",
            "dest_path": "/top/other"
        }
        resp = await self.client.put("/folder/move.json", json=payload)
        self.assertEqual(resp.status, 200)
        f = folder.find("/top/other/leaf", db)
        self.assertEqual(f.streams[0].name, "stream1")
        self.assertIsNone(folder.find("/top/leaf", db))

    @unittest_run_loop
    async def test_folder_move_by_id(self):
        db: Session = self.app["db"]
        # move stream1 into folder3
        dest_folder = folder.find("/top/middle/leaf", db)
        src_folder = folder.find("/top/leaf", db)
        payload = {
            "src_id": src_folder.id,
            "dest_id": dest_folder.id
        }
        resp = await self.client.put("/folder/move.json", json=payload)
        self.assertEqual(resp.status, 200)
        self.assertEqual(src_folder.id,
                         folder.find("/top/middle/leaf/leaf", db).id)
        self.assertIsNone(folder.find("/top/leaf", db))

    @unittest_run_loop
    async def test_folder_delete_by_path(self):
        db: Session = self.app["db"]
        f = folder.find("/top/leaf", db)
        payload = {'path': "/top/leaf"}
        resp = await self.client.delete("/folder.json", params=payload)
        self.assertEqual(resp.status, 200)

        self.assertIsNone(folder.find("/top/leaf", db))
        # deletes the streams
        self.assertIsNone(folder.find_stream_by_path("/top/leaf/stream1", db))
        # keeps the parent folders
        self.assertIsNotNone(folder.find("/top", db))

    @unittest_run_loop
    async def test_folder_delete_by_id(self):
        db: Session = self.app["db"]
        f_count = db.query(Folder).count()
        f = folder.find("/an/empty/folder", db, create=True)
        self.assertEqual(db.query(Folder).count(), f_count + 3)
        payload = {'id': f.id}
        resp = await self.client.delete("/folder.json", params=payload)
        self.assertEqual(resp.status, 200)

        self.assertIsNone(folder.find("/an/empty/folder", db))
        # keeps the parent folders
        self.assertEqual(f_count + 2, db.query(Folder).count())
        self.assertIsNotNone(folder.find("/an/empty", db))

    @unittest_run_loop
    async def test_folder_recursive_delete(self):
        db: Session = self.app["db"]
        f = folder.find("/top", db)
        payload = {'path': "/top", 'recursive': "1"}
        resp = await self.client.delete("/folder.json", params=payload)
        self.assertEqual(resp.status, 200)
        # this is the top folder so everything should be gone
        self.assertEqual(1, db.query(Folder).count())
        self.assertEqual(0, db.query(Stream).count())
        self.assertEqual(0, db.query(Element).count())

    @unittest_run_loop
    async def test_folder_update(self):
        db: Session = self.app["db"]
        my_folder = folder.find("/top/middle/leaf", db)
        # change the stream name
        payload = {
            "id": my_folder.id,
            "folder": {"name": "new name", "description": "new description"}
        }
        resp = await self.client.put("/folder.json", json=payload)
        self.assertEqual(200, resp.status)
        my_folder: Stream = db.query(Folder).get(my_folder.id)
        self.assertEqual("new name", my_folder.name)
        self.assertEqual("new description", my_folder.description)
