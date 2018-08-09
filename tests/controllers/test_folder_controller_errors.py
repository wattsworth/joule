from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web
from sqlalchemy.orm import Session
import json

from joule.models import folder, Stream, Folder
import joule.controllers
from .helpers import create_db, MockStore


class TestFolderControllerErrors(AioHTTPTestCase):

    async def get_application(self):
        app = web.Application()
        app.add_routes(joule.controllers.routes)
        app["db"] = create_db(["/top/leaf/stream1:float32[x, y, z]",
                               "/top/middle/leaf/stream2:int8[val1, val2]"])
        app["data-store"] = MockStore()
        return app

    @unittest_run_loop
    async def test_folder_move(self):
        db: Session = self.app["db"]
        # must specify an id or a path
        resp = await self.client.put("/folder/move.json", data={"destination": "/new/location"})
        self.assertEqual(resp.status, 400)
        # must specify a destination
        resp = await self.client.put("/folder/move.json", data={"path": "/top/leaf"})
        self.assertEqual(resp.status, 400)
        # return "not found" on bad id
        resp = await self.client.put("/folder/move.json", data={"id": 2348,
                                                                "destination": "/x/y"})
        self.assertEqual(resp.status, 404)
        # return "not found" on bad path
        resp = await self.client.put("/folder/move.json", data={"path": "/missing/folder",
                                                                "destination": "/x/y"})
        self.assertEqual(resp.status, 404)
        # error on bad destination
        resp = await self.client.put("/folder/move.json", data={"path": "/top/leaf",
                                                                "destination": "malformed"})
        self.assertEqual(resp.status, 400)

        # cannot conflict with an existing folder in the destination
        resp = await self.client.put("/folder/move.json", data={"path": "/top/leaf",
                                                                "destination": "/top/middle"})
        self.assertEqual(resp.status, 400)

        # cannot move a folder into its children
        resp = await self.client.put("/folder/move.json", data={"path": "/top",
                                                                "destination": "/top/leaf"})
        self.assertEqual(resp.status, 400)
        self.assertTrue('parent' in await resp.text())
        self.assertIsNotNone(folder.find('/top/middle/leaf', db))

        # cannot move folders with locked streams
        my_stream: Stream = db.query(Stream).filter_by(name="stream1").one()
        my_stream.is_configured = True
        resp = await self.client.put("/folder/move.json", data={"path": "/top/leaf",
                                                                "destination": "/top/middle"})
        self.assertEqual(resp.status, 400)
        self.assertTrue('locked' in await resp.text())

    @unittest_run_loop
    async def test_folder_delete(self):
        db: Session = self.app["db"]

        resp = await self.client.delete("/folder.json", params={})
        self.assertEqual(resp.status, 400)
        # return "not found" on bad id
        resp = await self.client.delete("/folder.json", params={"id": 2348})
        self.assertEqual(resp.status, 404)
        # return "not found" on bad path
        resp = await self.client.delete("/folder.json", params={"path": "/bad/path"})
        self.assertEqual(resp.status, 404)
        # cannot delete folders with streams
        resp = await self.client.delete("/folder.json", params={"path": "/top/leaf"})
        self.assertEqual(resp.status, 400)
        self.assertTrue('streams' in await resp.text())
        self.assertIsNotNone(db.query(Stream).filter_by(name="stream1").one())
        # cannot delete folders with children unless recursive is set
        f = folder.find("/a/new/path", db, create=True)
        resp = await self.client.delete("/folder.json", params={"path": "/a"})
        self.assertEqual(resp.status, 400)
        self.assertTrue('recursive' in await resp.text())
        self.assertIsNotNone(db.query(Folder).get(f.id))

    @unittest_run_loop
    async def test_folder_update(self):
        db: Session = self.app["db"]
        my_folder = folder.find("/top/middle", db)
        # invalid name, nothing should be saved
        payload = {
            "id": my_folder.id,
            "folder": json.dumps(
                {"name": "",
                 "description": "new description"})
        }
        resp = await self.client.put("/folder.json", data=payload)
        self.assertEqual(resp.status, 400)
        self.assertTrue('name' in await resp.text())
        my_folder = folder.find("/top/middle", db)
        self.assertEqual("middle", my_folder.name)

        # request must specify an id
        payload = {
            "folder": json.dumps({"name": "new name"})
        }
        resp = await self.client.put("/folder.json", data=payload)
        self.assertEqual(resp.status, 400)
        self.assertTrue('id' in await resp.text())

        # request must have folder attr
        payload = {
            "id": my_folder.id
        }
        resp = await self.client.put("/folder.json", data=payload)
        self.assertEqual(resp.status, 400)
        self.assertTrue('folder' in await resp.text())

        # folder attr must be valid json
        payload = {
            "id": my_folder.id,
            "folder": "notjson"
        }
        resp = await self.client.put("/folder.json", data=payload)
        self.assertEqual(resp.status, 400)
        self.assertTrue('JSON' in await resp.text())

        # cannot modify locked streams
        my_folder.children[0].streams[0].is_configured = True
        payload = {
            "id": my_folder.id,
            "folder": json.dumps({"name": "new name"})
        }
        resp = await self.client.put("/folder.json", data=payload)
        self.assertEqual(resp.status, 400)
        self.assertTrue('locked' in await resp.text())

        # folder must exist
        payload = {
            "id": 4898,
            "stream": json.dumps({"name": "new name"})
        }
        resp = await self.client.put("/folder.json", data=payload)
        self.assertEqual(resp.status, 404)
        self.assertTrue('exist' in await resp.text())

