from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web
import aiohttp

import joule.controllers
from tests.controllers.helpers import MockStore


class TestRootController(AioHTTPTestCase):

    async def get_application(self):
        app = web.Application()
        app.add_routes(joule.controllers.routes)
        app["data-store"] = MockStore()
        app["name"] = "test_suite"
        return app


    async def test_index(self):
        resp: aiohttp.ClientResponse = await self.client.request("GET", "/")
        msg = await resp.text()
        self.assertEqual(resp.status, 200)
        # 'joule' is somewhere in the response string
        self.assertTrue('joule' in msg.lower())


    async def test_version(self):
        resp: aiohttp.ClientResponse = await self.client.request("GET", "/version")
        version = await resp.text()
        self.assertEqual(resp.status, 200)
        # version is some non-empty string
        self.assertTrue(len(version) > 0)
        # check JSON version
        resp: aiohttp.ClientResponse = await self.client.request("GET", "/version.json")
        data = await resp.json()
        self.assertEqual(resp.status, 200)
        # version is some non-empty string
        self.assertTrue(len(data['version']) > 0)


    async def test_dbinfo(self):
        resp: aiohttp.ClientResponse = await self.client.request("GET", "/dbinfo")
        dbinfo = await resp.json()
        self.assertEqual(resp.status, 200)
        # check one of the keys to make sure this is a dbinfo object
        self.assertTrue('path' in dbinfo)
