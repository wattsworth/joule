from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from sqlalchemy.orm import Session
from aiohttp import web
import aiohttp
import json

from joule.models import Stream, Element
import joule.controllers
from .helpers import create_db, MockStore


class TestStreamControllerErrors(AioHTTPTestCase):

    async def tearDownAsync(self):
        self.app["db"].close()
        self.app["psql"].stop()

    async def get_application(self):
        app = web.Application()
        app.add_routes(joule.controllers.routes)
        app["db"], app["psql"] = create_db(["/folder1/stream1:float32[x, y, z]",
                                            "/folder2/deeper/stream2:int8[val1, val2]",
                                            "/folder_x1/same_name:float32[x, y, z]",
                                            "/folder_x2/same_name:int8[val1, val2]"
                                            ])
        app["data-store"] = MockStore()
        return app

    @unittest_run_loop
    async def test_stream_info(self):
        # must specify an id or a path
        resp: aiohttp.ClientResponse = await self.client.request("GET", "/stream.json")
        self.assertEqual(resp.status, 400)
        # return "not found" on bad id
        resp: aiohttp.ClientResponse = await self.client.request("GET", "/stream.json?id=2348")
        self.assertEqual(resp.status, 404)
        # return "not found" on bad path
        payload = {'path': "/bad/path"}
        resp = await self.client.request("GET", "/stream.json", params=payload)
        self.assertEqual(resp.status, 404)

    @unittest_run_loop
    async def test_stream_move(self):
        db: Session = self.app["db"]

        # must specify an id or a path
        resp = await self.client.put("/stream/move.json", json={"dest_path": "/new/folder3"})
        self.assertEqual(resp.status, 400)
        # must specify a destination
        resp = await self.client.put("/stream/move.json", json={"src_path": "/folder1/stream1"})
        self.assertEqual(resp.status, 400)
        # return "not found" on bad id
        resp = await self.client.put("/stream/move.json", json={"src_id": 2348,
                                                                "dest_path": "/x/y"})
        self.assertEqual(resp.status, 404)
        # return "not found" on bad path
        resp = await self.client.put("/stream/move.json", json={"src_path": "/folder2/deeper",
                                                                "dest_path": "/x/y"})
        self.assertEqual(resp.status, 404)
        # error on bad destination
        resp = await self.client.put("/stream/move.json", json={"src_path": "/folder2/deeper",
                                                                "dest_path": "malformed"})
        self.assertEqual(resp.status, 404)
        resp = await self.client.put("/stream/move.json", json={"src_path": "/folder1/stream1",
                                                                "dest_path": "invalid"})
        self.assertEqual(resp.status, 400)

        # cannot conflict with an existing stream in the destination
        resp = await self.client.put("/stream/move.json", json={"src_path": "/folder_x1/same_name",
                                                                "dest_path": "/folder_x2"})
        self.assertEqual(resp.status, 400)
        # cannot move streams with a fixed configuration
        my_stream: Stream = db.query(Stream).filter_by(name="stream1").one()
        my_stream.is_configured = True
        resp = await self.client.put("/stream/move.json", json={"src_path": "/folder1/stream1",
                                                                "dest_path": "/folder8"})
        self.assertEqual(resp.status, 400)
        self.assertTrue('locked' in await resp.text())

    @unittest_run_loop
    async def test_stream_create(self):
        # must specify a stream
        resp = await self.client.post("/stream.json", json={"path": "/folder2/deeper"})
        self.assertEqual(resp.status, 400)
        # must specify a path
        new_stream = Stream(name="test", datatype=Stream.DATATYPE.FLOAT32)
        new_stream.elements = [Element(name="e%d" % j, index=j,
                                       display_type=Element.DISPLAYTYPE.CONTINUOUS) for j in range(3)]
        resp = await self.client.post("/stream.json", json={"stream": new_stream.to_json()})
        self.assertEqual(resp.status, 400)
        # invalid stream json
        resp = await self.client.post("/stream.json", json={"path": "/path/to",
                                                            "stream": 'notjson'})
        self.assertEqual(resp.status, 400)
        # incorrect stream format
        resp = await self.client.post("/stream.json", json={"path": "/path/to",
                                                            "stream": '{"invalid": 2}'})
        self.assertEqual(resp.status, 400)

    @unittest_run_loop
    async def test_stream_delete(self):
        db: Session = self.app["db"]

        resp = await self.client.delete("/stream.json", params={})
        self.assertEqual(resp.status, 400)
        # return "not found" on bad id
        resp = await self.client.delete("/stream.json", params={"id": 2348})
        self.assertEqual(resp.status, 404)
        # return "not found" on bad path
        resp = await self.client.delete("/stream.json", params={"path": "/bad/path"})
        self.assertEqual(resp.status, 404)
        # cannot delete locked streams
        my_stream: Stream = db.query(Stream).filter_by(name="stream1").one()
        my_stream.is_configured = True
        resp = await self.client.delete("/stream.json", params={"id": my_stream.id})
        self.assertEqual(resp.status, 400)
        self.assertTrue('locked' in await resp.text())
        self.assertIsNotNone(db.query(Stream).filter_by(name="stream1").one())

    @unittest_run_loop
    async def test_stream_update(self):
        db: Session = self.app["db"]
        my_stream: Stream = db.query(Stream).filter_by(name="stream1").one()
        # invalid element display_type, nothing should be saved
        payload = {
            "id": my_stream.id,
            "stream": json.dumps(
                {"name": "new name",
                 "elements": [{"display_type": "invalid", "name": "new"},
                              {"name": "new1"},
                              {"name": "new3"}]})
        }
        resp = await self.client.put("/stream.json", data=payload)
        self.assertEqual(resp.status, 400)
        self.assertTrue('display_type' in await resp.text())

        my_stream: Stream = db.query(Stream).get(my_stream.id)
        self.assertEqual("stream1", my_stream.name)
        elem_0 = [e for e in my_stream.elements if e.index == 0][0]
        self.assertEqual(elem_0.display_type, Element.DISPLAYTYPE.CONTINUOUS)
        self.assertEqual(elem_0.name, 'x')

        # request must specify an id
        payload = {
            "stream": json.dumps({"name": "new name"})
        }
        resp = await self.client.put("/stream.json", data=payload)
        self.assertEqual(resp.status, 400)
        self.assertTrue('id' in await resp.text())

        # request must have streams attr
        payload = {
            "id": my_stream.id
        }
        resp = await self.client.put("/stream.json", data=payload)
        self.assertEqual(resp.status, 400)
        self.assertTrue('stream' in await resp.text())

        # streams attr must be valid json
        payload = {
            "id": my_stream.id,
            "stream": "notjson"
        }
        resp = await self.client.put("/stream.json", data=payload)
        self.assertEqual(resp.status, 400)
        self.assertTrue('JSON' in await resp.text())

        # cannot modify locked streams
        my_stream.is_configured = True
        payload = {
            "id": my_stream.id,
            "stream": json.dumps({"name": "new name"})
        }
        resp = await self.client.put("/stream.json", data=payload)
        self.assertEqual(resp.status, 400)
        self.assertTrue('locked' in await resp.text())

        # stream must exist
        payload = {
            "id": 4898,
            "stream": json.dumps({"name": "new name"})
        }
        resp = await self.client.put("/stream.json", data=payload)
        self.assertEqual(resp.status, 404)
        self.assertTrue('exist' in await resp.text())
