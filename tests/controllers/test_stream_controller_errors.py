from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web
import aiohttp

from joule.models import Stream, Element
import joule.controllers
from .helpers import create_db, MockStore


class TestStreamControllerErrors(AioHTTPTestCase):

    async def get_application(self):
        app = web.Application()
        app.add_routes(joule.controllers.routes)
        app["db"] = create_db(["/folder1/stream1:float32[x, y, z]",
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
        # must specify an id or a path
        resp = await self.client.put("/stream/move.json", data={"destination": "/new/folder3"})
        self.assertEqual(resp.status, 400)
        # must specify a destination
        resp = await self.client.put("/stream/move.json", data={"path": "/folder1/stream1"})
        self.assertEqual(resp.status, 400)
        # return "not found" on bad id
        resp = await self.client.put("/stream/move.json", data={"id": 2348,
                                                                "destination": "/x/y"})
        self.assertEqual(resp.status, 404)
        # return "not found" on bad path
        resp = await self.client.put("/stream/move.json", data={"path": "/folder2/deeper",
                                                                "destination": "/x/y"})
        self.assertEqual(resp.status, 404)
        # error on bad destination
        resp = await self.client.put("/stream/move.json", data={"path": "/folder2/deeper",
                                                                "destination": "malformed"})
        self.assertEqual(resp.status, 404)
        # cannot conflict with an existing stream in the destination
        resp = await self.client.put("/stream/move.json", data={"path": "/folder_x1/same_name",
                                                                "destination": "/folder_x2"})
        self.assertEqual(resp.status, 400)

    @unittest_run_loop
    async def test_stream_create(self):
        # must specify a stream
        resp = await self.client.post("/stream.json", data={"path": "/folder2/deeper"})
        self.assertEqual(resp.status, 400)
        # must specify a path
        new_stream = Stream(name="test", datatype=Stream.DATATYPE.FLOAT32)
        new_stream.elements = [Element(name="e%d" % j, index=j,
                                       display_type=Element.DISPLAYTYPE.CONTINUOUS) for j in range(3)]
        resp = await self.client.post("/stream.json", data={"stream": new_stream.to_json()})
        self.assertEqual(resp.status, 400)
        # invalid stream json
        resp = await self.client.post("/stream.json", data={"path": "/path/to",
                                                            "stream": 'notjson'})
        self.assertEqual(resp.status, 400)
        # incorrect stream format
        resp = await self.client.post("/stream.json", data={"path": "/path/to",
                                                            "stream": '{"invalid": 2}'})
        self.assertEqual(resp.status, 400)

    @unittest_run_loop
    async def test_stream_delete(self):
        resp = await self.client.delete("/stream.json", params = {})
        self.assertEqual(resp.status, 400)
        # return "not found" on bad id
        resp = await self.client.delete("/stream.json", params={"id": 2348})
        self.assertEqual(resp.status, 404)
        # return "not found" on bad path
        resp = await self.client.delete("/stream.json", params={"path": "/bad/path"})
        self.assertEqual(resp.status, 404)
