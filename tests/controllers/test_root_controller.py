from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web
import aiohttp
import uuid

import joule.controllers
from joule.constants import EndPoints
from tests.controllers.helpers import MockStore
from joule import app_keys
from joule.utilities import ConnectionInfo

class TestRootController(AioHTTPTestCase):

    async def get_application(self):
        app = web.Application()
        app.add_routes(joule.controllers.routes)
        app[app_keys.data_store] = MockStore()
        app[app_keys.name] = "test_suite"
        app[app_keys.uuid] = uuid.uuid4()
        self.connection_info = ConnectionInfo(username="test",
                                            password="test", 
                                            port=5432, 
                                            database="test", 
                                            host="test")
        app[app_keys.module_connection_info] = self.connection_info
        return app


    async def test_index(self):
        resp: aiohttp.ClientResponse = await self.client.request("GET", "/")
        msg = await resp.text()
        self.assertEqual(resp.status, 200)
        # 'joule' is somewhere in the response string
        self.assertTrue('joule' in msg.lower())


    async def test_version(self):
        resp: aiohttp.ClientResponse = await self.client.request("GET", EndPoints.version)
        version = await resp.text()
        self.assertEqual(resp.status, 200)
        # version is some non-empty string
        self.assertTrue(len(version) > 0)
        # check JSON version
        resp: aiohttp.ClientResponse = await self.client.request("GET", EndPoints.version_json)
        data = await resp.json()
        self.assertEqual(resp.status, 200)
        # version is some non-empty string
        self.assertTrue(len(data['version']) > 0)


    async def test_dbinfo(self):
        resp: aiohttp.ClientResponse = await self.client.request("GET", EndPoints.db_info)
        dbinfo = await resp.json()
        self.assertEqual(resp.status, 200)
        # check one of the keys to make sure this is a dbinfo object
        self.assertTrue('path' in dbinfo)

    async def test_db_connection(self):
        resp: aiohttp.ClientResponse = await self.client.request("GET", EndPoints.db_connection)
        dbinfo = await resp.json()
        self.assertEqual(resp.status, 200)
        self.assertDictEqual(dbinfo, self.connection_info.to_json())
