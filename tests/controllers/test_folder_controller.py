from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web
from sqlalchemy.orm import Session
import json

from joule.models import folder, Stream, Folder
import joule.controllers
from .helpers import create_db, MockStore


class TestFolderController(AioHTTPTestCase):

    async def get_application(self):
        app = web.Application()
        app.add_routes(joule.controllers.routes)
        app["db"] = create_db(["/top/leaf/stream1:float32[x, y, z]",
                               "/top/middle/leaf/stream2:int8[val1, val2]"])
        app["data-store"] = MockStore()
        return app

    @unittest_run_loop
    async def test_folder_move_by_path(self):
        db: Session = self.app["db"]
        # move stream1 into folder3
        payload = {
            "path": "/top/leaf",
            "destination": "/top/other"
        }
        resp = await self.client.put("/folder/move.json", data=payload)
        self.assertEqual(resp.status, 200)
        f = folder.find("/top/other/leaf", db)
        self.assertEqual(f.streams[0].name, "stream1")
        self.assertIsNone(folder.find("/top/leaf", db))

    @unittest_run_loop
    async def test_folder_move_by_id(self):
        db: Session = self.app["db"]
        # move stream1 into folder3
        payload = {
            "id": folder.find("/top/leaf", db).id,
            "destination": "/top/other"
        }
        resp = await self.client.put("/folder/move.json", data=payload)
        self.assertEqual(resp.status, 200)
        f = folder.find("/top/other/leaf", db)
        self.assertEqual(f.streams[0].name, "stream1")
        self.assertIsNone(folder.find("/top/leaf", db))

    @unittest_run_loop
    async def test_folder_delete_by_path(self):
        db: Session = self.app["db"]
        f_count = db.query(Folder).count()
        folder.find("/an/empty/folder", db, create=True)
        self.assertEqual(db.query(Folder).count(), f_count + 3)
        payload = {'path': "/an/empty/folder"}
        resp = await self.client.delete("/folder.json", params=payload)
        self.assertEqual(resp.status, 200)

        self.assertIsNone(folder.find("/an/empty/folder", db))
        # keeps the parent folders
        self.assertEqual(f_count + 2, db.query(Folder).count())
        self.assertIsNotNone(folder.find("/an/empty", db))

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
        f_count = db.query(Folder).count()
        folder.find("/an/empty/folder", db, create=True)
        self.assertEqual(db.query(Folder).count(), f_count + 3)
        payload = {'path': "/an", 'recursive': "True"}
        resp = await self.client.delete("/folder.json", params=payload)
        self.assertEqual(resp.status, 200)

        self.assertIsNone(folder.find("/an", db))
        # removes all the children
        self.assertEqual(f_count, db.query(Folder).count())
        self.assertIsNone(folder.find("/an/empty", db))

    @unittest_run_loop
    async def test_folder_update(self):
        db: Session = self.app["db"]
        my_folder = folder.find("/top/middle/leaf", db)
        # change the stream name
        payload = {
            "id": my_folder.id,
            "folder": json.dumps({"name": "new name", "description": "new description"})
        }
        resp = await self.client.put("/folder.json", data=payload)
        self.assertEqual(200, resp.status)
        my_folder: Stream = db.query(Folder).get(my_folder.id)
        self.assertEqual("new name", my_folder.name)
        self.assertEqual("new description", my_folder.description)
