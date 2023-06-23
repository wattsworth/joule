from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from sqlalchemy.orm import Session
from aiohttp import web
import aiohttp
import asyncio
import datetime

from joule.models import DataStream, Element
import joule.controllers
from tests.controllers.helpers import create_db, MockStore

class TestStreamControllerErrors(AioHTTPTestCase):

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
        app["db"], app["psql"] = create_db(["/folder1/stream1:float32[x, y, z]",
                                            "/folder1/same_name:float32[x, y, z]",
                                            "/folder2/deeper/stream2:int8[val1, val2]",
                                            "/folder_x1/same_name:float32[x, y, z]",
                                            "/folder_x2/same_name:int8[val1, val2]"
                                            ])
        app["data-store"] = MockStore()
        return app


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


    async def test_stream_move(self):
        db: Session = self.app["db"]

        # must be json
        resp = await self.client.put("/stream/move.json", data={"dest_path": "/new/folder3"})
        self.assertEqual(resp.status, 400)
        self.assertIn("json", await resp.text())
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
        my_stream: DataStream = db.query(DataStream).filter_by(name="stream1").one()
        my_stream.is_configured = True
        resp = await self.client.put("/stream/move.json", json={"src_path": "/folder1/stream1",
                                                                "dest_path": "/folder8"})
        self.assertEqual(resp.status, 400)
        self.assertTrue('locked' in await resp.text())


    async def test_stream_create(self):
        # must be json
        resp = await self.client.post("/stream.json", data={"bad_values": "not_json"})
        self.assertEqual(resp.status, 400)
        self.assertIn("json", await resp.text())

        # must specify a stream
        resp = await self.client.post("/stream.json", json={"dest_path": "/folder2/deeper"})
        self.assertEqual(resp.status, 400)
        # invalid dest_path
        resp = await self.client.post("/stream.json", json={"dest_path": "notapath"})
        self.assertEqual(resp.status, 400)
        # must specify a path
        new_stream = DataStream(name="test", datatype=DataStream.DATATYPE.FLOAT32,
                      updated_at=datetime.datetime.utcnow())
        new_stream.elements = [Element(name="e%d" % j, index=j,
                                       display_type=Element.DISPLAYTYPE.CONTINUOUS) for j in range(3)]
        resp = await self.client.post("/stream.json", json={"stream": new_stream.to_json()})
        self.assertEqual(resp.status, 400)
        # element names must be unique
        e1_name = new_stream.elements[1].name
        new_stream.elements[1].name = new_stream.elements[2].name
        resp = await self.client.post("/stream.json", json={
            "dest_path": "/folder2/deeper",
            "stream": new_stream.to_json()})
        self.assertEqual(resp.status, 400)
        self.assertIn("names must be unique", await resp.text())
        new_stream.elements[1].name = e1_name  # restore the original name

        # stream must have a unique name in the folder
        new_stream.name = "stream1"
        resp = await self.client.post("/stream.json", json={"stream": new_stream.to_json(),
                                                            "dest_path": "/folder1"})
        self.assertEqual(resp.status, 400)
        self.assertIn("same name", await resp.text())
        # invalid dest_path
        resp = await self.client.post("/stream.json", json={"stream": new_stream.to_json(),
                                                            "dest_path": "notapath"})
        self.assertEqual(resp.status, 400)
        # stream must have a name
        new_stream.name = ""
        resp = await self.client.post("/stream.json", json={"stream": new_stream.to_json(),
                                                            "dest_path": "/a/valid/path"})
        self.assertEqual(resp.status, 400)
        self.assertIn("name", await resp.text())
        new_stream.name = "test"
        # stream must have at least one element
        new_stream.elements = []
        resp = await self.client.post("/stream.json", json={"stream": new_stream.to_json(),
                                                            "dest_path": "/a/valid/path"})
        self.assertEqual(resp.status, 400)
        self.assertIn("element", await resp.text())

        # invalid stream json (test all different exception paths)
        resp = await self.client.post("/stream.json", json={"dest_path": "/path/to",
                                                            "stream": 'notjson'})
        self.assertEqual(resp.status, 400)
        self.assertIn("JSON", await resp.text())

        json = new_stream.to_json()
        json["datatype"] = "invalid"
        resp = await self.client.post("/stream.json", json={"dest_path": "/path/to",
                                                            "stream": json})
        self.assertEqual(resp.status, 400)
        self.assertIn("specification", await resp.text())
        self.assertIn("datatype", await resp.text())

        del json["datatype"]
        resp = await self.client.post("/stream.json", json={"dest_path": "/path/to",
                                                            "stream": json})
        self.assertEqual(resp.status, 400)
        self.assertIn("datatype", await resp.text())

        # incorrect stream format
        resp = await self.client.post("/stream.json", json={"path": "/path/to",
                                                            "stream": '{"invalid": 2}'})
        self.assertEqual(resp.status, 400)


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
        my_stream: DataStream = db.query(DataStream).filter_by(name="stream1").one()
        my_stream.is_configured = True
        resp = await self.client.delete("/stream.json", params={"id": my_stream.id})
        self.assertEqual(resp.status, 400)
        self.assertTrue('locked' in await resp.text())
        self.assertIsNotNone(db.query(DataStream).filter_by(name="stream1").one())


    async def test_stream_update(self):
        db: Session = self.app["db"]
        my_stream: DataStream = db.query(DataStream).filter_by(name="stream1").one()

        # must be json
        resp = await self.client.put("/stream.json", data={"bad_values": "not_json"})
        self.assertEqual(resp.status, 400)
        self.assertIn("json", await resp.text())

        # invalid element display_type, nothing should be saved
        payload = {
            "id": my_stream.id,
            "stream":
                {"name": "new name",
                 "elements": [{"display_type": "invalid", "name": "new"},
                              {"name": "new1"},
                              {"name": "new3"}]}
        }
        resp = await self.client.put("/stream.json", json=payload)
        self.assertEqual(resp.status, 400)
        self.assertTrue('display_type' in await resp.text())

        my_stream: DataStream = db.get(DataStream, my_stream.id)
        self.assertEqual("stream1", my_stream.name)
        elem_0 = [e for e in my_stream.elements if e.index == 0][0]
        self.assertEqual(elem_0.display_type, Element.DISPLAYTYPE.CONTINUOUS)
        self.assertEqual(elem_0.name, 'x')

        # request must specify an id
        payload = {
            "stream": {"name": "new name"}
        }
        resp = await self.client.put("/stream.json", json=payload)
        self.assertEqual(resp.status, 400)
        self.assertTrue('id' in await resp.text())

        # request must have streams attr
        payload = {
            "id": my_stream.id
        }
        resp = await self.client.put("/stream.json", json=payload)
        self.assertEqual(resp.status, 400)
        self.assertTrue('stream' in await resp.text())

        # streams attr must be valid json
        payload = {
            "id": my_stream.id,
            "stream": "notjson"
        }
        resp = await self.client.put("/stream.json", json=payload)
        self.assertEqual(resp.status, 400)
        self.assertTrue('JSON' in await resp.text())

        # cannot modify locked streams
        my_stream.is_configured = True
        payload = {
            "id": my_stream.id,
            "stream": {"name": "new name"}
        }
        resp = await self.client.put("/stream.json", json=payload)
        self.assertEqual(resp.status, 400)
        self.assertTrue('locked' in await resp.text())

        # stream must exist
        payload = {
            "id": 4898,
            "stream": {"name": "new name"}
        }
        resp = await self.client.put("/stream.json", json=payload)
        self.assertEqual(resp.status, 404)
        self.assertTrue('exist' in await resp.text())

        # stream name must be unique in the folder
        my_stream.is_configured = False  # unlock
        payload = {
            "id": my_stream.id,
            "stream": {"name": "same_name"}
        }
        resp = await self.client.put("/stream.json", json=payload)
        self.assertEqual(resp.status, 400)
        self.assertIn('same name', await resp.text())
