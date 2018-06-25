from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web
import aiohttp
from sqlalchemy.orm import Session

from joule.models import folder, Stream
import joule.controllers
from .helpers import create_db, MockStore


class TestStreamControllerErrors(AioHTTPTestCase):

    async def get_application(self):
        app = web.Application()
        app.add_routes(joule.controllers.routes)
        app["db"] = create_db(["/folder1/stream1:float32[x, y, z]",
                               "/folder2/deeper/stream2:int8[val1, val2]"])
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

