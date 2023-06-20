from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web
from sqlalchemy.orm import Session
import json
import asyncio
from joule.models import folder, DataStream, Folder
import joule.controllers
from tests.controllers.helpers import create_db, MockStore, MockEventStore


class TestFolderControllerErrors(AioHTTPTestCase):

    async def tearDownAsync(self):
        self.app["db"].close()
        self.app["psql"].stop()
        await self.client.close()

    async def get_application(self):
        app = web.Application()
        app.add_routes(joule.controllers.routes)
        # this takes a while, adjust the expected coroutine execution time
        loop = asyncio.get_running_loop()
        loop.slow_callback_duration = 2.0
        app["db"], app["psql"] = create_db(["/top/leaf/stream1:float32[x, y, z]",
                                            "/top/same_name/stream3:float32[x, y, z]",
                                            "/top/middle/leaf/stream2:int8[val1, val2]"])
        app["data-store"] = MockStore()
        app["event-store"] = MockEventStore()
        return app


    async def test_folder_info(self):
        # must specify an id or path
        resp = await self.client.get("/folder.json", params={})
        self.assertEqual(resp.status, 400)
        self.assertIn("specify an id or path", await resp.text())

        # folder must exist
        resp = await self.client.get("/folder.json", params={"id": 2343})
        self.assertEqual(resp.status, 404)
        self.assertIn("does not exist", await resp.text())


    async def test_folder_move(self):
        db: Session = self.app["db"]

        # must be a json request
        resp = await self.client.put("/folder/move.json", data={"dest_path": "/new/location"})
        self.assertEqual(resp.status, 400)
        self.assertIn("json", await resp.text())

        # must specify an id or a path
        resp = await self.client.put("/folder/move.json", json={"dest_path": "/new/location"})
        self.assertEqual(resp.status, 400)
        # must specify a destination
        resp = await self.client.put("/folder/move.json", json={"src_path": "/top/leaf"})
        self.assertEqual(resp.status, 400)
        # return "not found" on bad id
        resp = await self.client.put("/folder/move.json", json={"src_id": 2348,
                                                                "dest_path": "/x/y"})
        self.assertEqual(resp.status, 404)
        # return "not found" on bad path
        resp = await self.client.put("/folder/move.json", json={"src_path": "/missing/folder",
                                                                "dest_patbh": "/x/y"})
        self.assertEqual(resp.status, 404)
        # error on bad destination
        resp = await self.client.put("/folder/move.json", json={"src_path": "/top/leaf",
                                                                "dest_path": "malformed"})
        self.assertEqual(resp.status, 400)

        # cannot conflict with an existing folder in the destination
        resp = await self.client.put("/folder/move.json", json={"src_path": "/top/leaf",
                                                                "dest_path": "/top/middle"})
        self.assertEqual(resp.status, 400)

        # cannot move a folder into its children
        resp = await self.client.put("/folder/move.json", json={"src_path": "/top",
                                                                "dest_path": "/top/leaf"})
        self.assertEqual(resp.status, 400)
        self.assertTrue('parent' in await resp.text())
        self.assertIsNotNone(folder.find('/top/middle/leaf', db))

        # cannot move folders with locked streams
        my_stream: DataStream = db.query(DataStream).filter_by(name="stream1").one()
        my_stream.is_configured = True
        resp = await self.client.put("/folder/move.json", json={"src_path": "/top/leaf",
                                                                "dest_path": "/top/middle"})
        self.assertEqual(resp.status, 400)
        self.assertTrue('locked' in await resp.text())


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
        # cannot delete folders with children unless recursive is set
        f = folder.find("/a/new/path", db, create=True)
        resp = await self.client.delete("/folder.json", params={"path": "/a"})
        self.assertEqual(resp.status, 400)
        self.assertTrue('recursive' in await resp.text())
        self.assertIsNotNone(db.get(Folder, f.id))
        # cannot delete locked folders
        my_folder = folder.find("/top/middle", db)
        my_folder.children[0].data_streams[0].is_configured = True
        resp = await self.client.delete("/folder.json", params={"path": "/top/middle"})
        self.assertEqual(resp.status, 400)
        self.assertIn("locked", await resp.text())



    async def test_folder_update(self):
        db: Session = self.app["db"]
        my_folder = folder.find("/top/middle", db)

        # must be a json request
        resp = await self.client.put("/folder.json", data={"bad": "notjson"})
        self.assertEqual(resp.status, 400)
        self.assertIn("json", await resp.text())

        # invalid name, nothing should be saved
        payload = {
            "id": my_folder.id,
            "folder":
                {"name": "",
                 "description": "new description"}
        }
        resp = await self.client.put("/folder.json", json=payload)
        self.assertEqual(resp.status, 400)
        self.assertTrue('name' in await resp.text())
        my_folder = folder.find("/top/middle", db)
        self.assertEqual("middle", my_folder.name)

        # request must specify an id
        payload = {
            "folder": json.dumps({"name": "new name"})
        }
        resp = await self.client.put("/folder.json", json=payload)
        self.assertEqual(resp.status, 400)
        self.assertTrue('id' in await resp.text())

        # request must have folder attr
        payload = {
            "id": my_folder.id
        }
        resp = await self.client.put("/folder.json", json=payload)
        self.assertEqual(resp.status, 400)
        self.assertTrue('folder' in await resp.text())

        # folder attr must be valid json
        payload = {
            "id": my_folder.id,
            "folder": "notjson"
        }
        resp = await self.client.put("/folder.json", json=payload)
        self.assertEqual(resp.status, 400)
        self.assertTrue('JSON' in await resp.text())

        # cannot modify locked streams
        my_folder.children[0].data_streams[0].is_configured = True
        payload = {
            "id": my_folder.id,
            "folder": json.dumps({"name": "new name"})
        }
        resp = await self.client.put("/folder.json", json=payload)
        self.assertEqual(resp.status, 400)
        self.assertTrue('locked' in await resp.text())
        my_folder.children[0].data_streams[0].is_configured = False

        # folder must exist
        payload = {
            "id": 4898,
            "stream": json.dumps({"name": "new name"})
        }
        resp = await self.client.put("/folder.json", json=payload)
        self.assertEqual(resp.status, 404)
        self.assertTrue('exist' in await resp.text())

        # folder name cannot conflict with a peer
        payload = {
            "id": my_folder.id,
            "folder":
                {"name": "same_name",
                 "description": "new description"}
        }
        resp = await self.client.put("/folder.json", json=payload)
        self.assertEqual(resp.status, 400)
        self.assertIn('folder with this name', await resp.text())
        my_folder = folder.find("/top/middle", db)
        self.assertEqual("middle", my_folder.name)
