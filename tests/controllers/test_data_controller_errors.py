from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web
import aiohttp
from sqlalchemy.orm import Session
import asyncio
from joule.models import DataStream
import joule.controllers
from tests.controllers.helpers import create_db, MockStore, MockSupervisor
from tests import helpers


class TestDataController(AioHTTPTestCase):

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
                                            "/folder2/deeper/stream2:int8[val1, val2]"])
        app["data-store"] = MockStore()
        self.supervisor = MockSupervisor()
        app["supervisor"] = self.supervisor
        return app


    async def test_read_requires_path_or_id(self):
        resp: aiohttp.ClientResponse = await \
            self.client.get("/data", params={})
        self.assertNotEqual(resp.status, 200)
        self.assertTrue('path' in await resp.text())


    async def test_read_errors_on_invalid_stream(self):
        resp: aiohttp.ClientResponse = await \
            self.client.get("/data", params={'path': '/no/stream'})
        self.assertEqual(resp.status, 404)
        resp: aiohttp.ClientResponse = await \
            self.client.get("/data", params={'id': '404'})
        self.assertEqual(resp.status, 404)


    async def test_read_errors_on_no_data(self):
        store: MockStore = self.app['data-store']
        store.configure_extract(0, no_data=True)
        params = {'path': '/folder1/stream1', 'decimation-level': 64}
        resp: aiohttp.ClientResponse = await self.client.get("/data", params=params)
        self.assertNotEqual(resp.status, 200)
        self.assertTrue('no data' in await resp.text())


    async def test_read_errors_on_decimation_failure(self):
        store: MockStore = self.app['data-store']
        store.configure_extract(10, decimation_error=True)
        params = {'path': '/folder1/stream1', 'decimation-level': 64}
        resp: aiohttp.ClientResponse = await self.client.get("/data", params=params)
        self.assertNotEqual(resp.status, 200)
        self.assertTrue('decimated' in await resp.text())


    async def test_read_errors_on_nilmdb_error(self):
        store: MockStore = self.app['data-store']
        store.configure_extract(10, data_error=True)
        params = {'path': '/folder1/stream1', 'decimation-level': 64}
        resp: aiohttp.ClientResponse = await self.client.get("/data", params=params)
        self.assertNotEqual(resp.status, 200)
        self.assertTrue('error' in await resp.text())


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


    async def test_subscribe_requires_path_or_id(self):
        resp: aiohttp.ClientResponse = await \
            self.client.get("/data", params={'subscribe': '1'})
        self.assertNotEqual(resp.status, 200)
        self.assertTrue('path' in await resp.text())


    async def test_subscribe_errors_on_invalid_stream(self):
        resp: aiohttp.ClientResponse = await \
            self.client.get("/data", params={'path': '/no/stream', 'subscribe': '1'})
        self.assertEqual(resp.status, 404)
        resp: aiohttp.ClientResponse = await \
            self.client.get("/data", params={'id': '404', 'subscribe': '1'})
        self.assertEqual(resp.status, 404)


    async def test_subscribe_errors_on_unproduced_stream(self):
        self.supervisor.raise_error = True
        resp: aiohttp.ClientResponse = await \
            self.client.get("/data", params={'path': '/folder1/stream1', 'subscribe': '1'})
        self.assertEqual(resp.status, 400)


    async def test_subscribe_does_not_support_json(self):
        resp: aiohttp.ClientResponse = await \
            self.client.get("/data.json", params={'path': '/folder1/stream1', 'subscribe': '1'})
        self.assertEqual(resp.status, 400)


    async def test_write_requires_path_or_id(self):
        resp: aiohttp.ClientResponse = await \
            self.client.post("/data", params={})
        self.assertNotEqual(resp.status, 200)
        self.assertTrue('path' in await resp.text())


    async def test_write_errors_on_invalid_stream(self):
        resp: aiohttp.ClientResponse = await \
            self.client.post("/data", params={'path': '/no/stream'})
        self.assertEqual(resp.status, 404)
        resp: aiohttp.ClientResponse = await \
            self.client.post("/data", params={'id': '404'})
        self.assertEqual(resp.status, 404)


    async def test_remove_requires_path_or_id(self):
        resp: aiohttp.ClientResponse = await \
            self.client.delete("/data", params={})
        self.assertNotEqual(resp.status, 200)
        self.assertTrue('path' in await resp.text())


    async def test_remove_errors_on_invalid_stream(self):
        resp: aiohttp.ClientResponse = await \
            self.client.delete("/data", params={'path': '/no/stream'})
        self.assertEqual(resp.status, 404)
        resp: aiohttp.ClientResponse = await \
            self.client.delete("/data", params={'id': '404'})
        self.assertEqual(resp.status, 404)


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


    async def test_intervals_requires_path_or_id(self):
        resp: aiohttp.ClientResponse = await \
            self.client.get("/data/intervals.json", params={})
        self.assertNotEqual(resp.status, 200)
        self.assertTrue('path' in await resp.text())


    async def test_intervals_errors_on_bad_stream(self):
        resp: aiohttp.ClientResponse = await \
            self.client.get("/data/intervals.json", params={'path': '/no/stream'})
        self.assertEqual(resp.status, 404)
        resp: aiohttp.ClientResponse = await \
            self.client.get("/data/intervals.json", params={'id': '404'})
        self.assertEqual(resp.status, 404)


    async def test_interval_bounds_must_be_valid(self):
        params = dict(path='/folder1/stream1')
        # start must be an int
        params['start'] = 'bad'
        resp: aiohttp.ClientResponse = await self.client.get("/data/intervals.json", params=params)
        self.assertNotEqual(resp.status, 200)
        self.assertTrue('start' in await resp.text())
        # end must be an int
        params['start'] = 100
        params['end'] = '200.5'
        resp: aiohttp.ClientResponse = await self.client.get("/data/intervals.json", params=params)
        self.assertNotEqual(resp.status, 200)
        self.assertTrue('end' in await resp.text())
        # start must be before end
        params['end'] = 50
        resp: aiohttp.ClientResponse = await self.client.get("/data/intervals.json", params=params)
        self.assertNotEqual(resp.status, 200)
        self.assertTrue('end' in await resp.text())
        self.assertTrue('start' in await resp.text())
        params['end'] = 200


    async def test_invalid_writes_propagates_data_error(self):
        db: Session = self.app["db"]
        store: MockStore = self.app['data-store']
        store.raise_data_error = True
        stream: DataStream = db.query(DataStream).filter_by(name="stream1").one()
        data = helpers.create_data(stream.layout)
        resp: aiohttp.ClientResponse = await \
            self.client.post("/data", params={"path": "/folder1/stream1"},
                             data=data.tobytes())
        self.assertEqual(resp.status, 400)
        self.assertIn(await resp.text(), 'test error')
