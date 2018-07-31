from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web
import aiohttp

import joule.controllers
from .helpers import create_db, MockStore


class TestDataController(AioHTTPTestCase):

    async def get_application(self):
        app = web.Application()
        app.add_routes(joule.controllers.routes)
        app["db"] = create_db(["/folder1/stream1:float32[x, y, z]",
                               "/folder2/deeper/stream2:int8[val1, val2]"])
        app["data-store"] = MockStore()
        return app

    @unittest_run_loop
    async def test_read_requires_path_or_id(self):
        resp: aiohttp.ClientResponse = await \
            self.client.get("/data", params={})
        self.assertNotEqual(resp.status, 200)
        self.assertTrue('path' in await resp.text())

    @unittest_run_loop
    async def test_read_errors_on_invalid_stream(self):
        resp: aiohttp.ClientResponse = await \
            self.client.get("/data", params={'path': '/no/stream'})
        self.assertEqual(resp.status, 404)
        resp: aiohttp.ClientResponse = await \
            self.client.get("/data", params={'id': '404'})
        self.assertEqual(resp.status, 404)

    @unittest_run_loop
    async def test_read_errors_on_decimation_failure(self):
        store: MockStore = self.app['data-store']
        store.configure_extract(10,decimation_error=True)
        params = {'path': '/folder1/stream1', 'decimation-level': 64}
        resp: aiohttp.ClientResponse = await self.client.get("/data", params=params)
        self.assertNotEqual(resp.status, 200)
        self.assertTrue('decimated' in await resp.text())

    @unittest_run_loop
    async def test_read_errors_on_nilmdb_error(self):
        store: MockStore = self.app['data-store']
        store.configure_extract(10, data_error=True)
        params = {'path': '/folder1/stream1', 'decimation-level': 64}
        resp: aiohttp.ClientResponse = await self.client.get("/data", params=params)
        self.assertNotEqual(resp.status, 200)
        self.assertTrue('error' in await resp.text())

    @unittest_run_loop
    async def test_read_params_must_be_valid(self):
        params = dict(path='/folder1/stream1')
        # start must be an int
        params['start'] = 'bad'
        resp: aiohttp.ClientResponse = await self.client.get("/data", params=params)
        self.assertNotEqual(resp.status, 200)
        self.assertTrue('start' in await resp.text())
        # end must be an int
        params['start'] = 100
        params['end'] = '200.5'
        resp: aiohttp.ClientResponse = await self.client.get("/data", params=params)
        self.assertNotEqual(resp.status, 200)
        self.assertTrue('end' in await resp.text())
        # start must be before end
        params['end'] = 50
        resp: aiohttp.ClientResponse = await self.client.get("/data", params=params)
        self.assertNotEqual(resp.status, 200)
        self.assertTrue('end' in await resp.text())
        self.assertTrue('start' in await resp.text())
        params['end'] = 200
        # max rows must be an int > 0
        params['max-rows'] = -4
        resp: aiohttp.ClientResponse = await self.client.get("/data", params=params)
        self.assertNotEqual(resp.status, 200)
        self.assertTrue('max-rows' in await resp.text())
        params['max-rows'] = 100
        # decimation-level must be >= 0
        params['decimation-level'] = -50
        resp: aiohttp.ClientResponse = await self.client.get("/data", params=params)
        self.assertNotEqual(resp.status, 200)
        self.assertTrue('decimation-level' in await resp.text())
        params['decimation-level'] = 20

    @unittest_run_loop
    async def test_write_requires_path_or_id(self):
        resp: aiohttp.ClientResponse = await \
            self.client.post("/data", params={})
        self.assertNotEqual(resp.status, 200)
        self.assertTrue('path' in await resp.text())

    @unittest_run_loop
    async def test_write_errors_on_invalid_stream(self):
        resp: aiohttp.ClientResponse = await \
            self.client.post("/data", params={'path': '/no/stream'})
        self.assertEqual(resp.status, 404)
        resp: aiohttp.ClientResponse = await \
            self.client.post("/data", params={'id': '404'})
        self.assertEqual(resp.status, 404)

    @unittest_run_loop
    async def test_remove_requires_path_or_id(self):
        resp: aiohttp.ClientResponse = await \
            self.client.delete("/data", params={})
        self.assertNotEqual(resp.status, 200)
        self.assertTrue('path' in await resp.text())

    @unittest_run_loop
    async def test_remove_errors_on_invalid_stream(self):
        resp: aiohttp.ClientResponse = await \
            self.client.delete("/data", params={'path': '/no/stream'})
        self.assertEqual(resp.status, 404)
        resp: aiohttp.ClientResponse = await \
            self.client.delete("/data", params={'id': '404'})
        self.assertEqual(resp.status, 404)

    @unittest_run_loop
    async def test_remove_bounds_must_be_valid(self):
        params = dict(path='/folder1/stream1')
        # start must be an int
        params['start'] = 'bad'
        resp: aiohttp.ClientResponse = await self.client.delete("/data", params=params)
        self.assertNotEqual(resp.status, 200)
        self.assertTrue('start' in await resp.text())
        # end must be an int
        params['start'] = 100
        params['end'] = '200.5'
        resp: aiohttp.ClientResponse = await self.client.delete("/data", params=params)
        self.assertNotEqual(resp.status, 200)
        self.assertTrue('end' in await resp.text())
        # start must be before end
        params['end'] = 50
        resp: aiohttp.ClientResponse = await self.client.delete("/data", params=params)
        self.assertNotEqual(resp.status, 200)
        self.assertTrue('end' in await resp.text())
        self.assertTrue('start' in await resp.text())
        params['end'] = 200
