from aiohttp.test_utils import AioHTTPTestCase
from aiohttp import web
import aiohttp
import json
import asyncio
import joule.controllers
from tests.controllers.helpers import create_db, MockSupervisor, MockWorker
from joule.models.proxy import Proxy
from joule.api.event_stream import EventStream as ApiEventStream, from_json as event_stream_from_json
from joule.api.event import Event
from joule import app_keys
from joule.constants import EndPoints

import testing.postgresql
psql_key = web.AppKey("psql", testing.postgresql.Postgresql)

class TestAppController(AioHTTPTestCase):

    async def tearDownAsync(self):
        self.app[app_keys.db].close()
        await asyncio.to_thread(self.app[psql_key].stop)
        await self.client.close()

    async def get_application(self):
        app = web.Application()
        app.add_routes(joule.controllers.routes)
        app[app_keys.db], app[psql_key] = await asyncio.to_thread(lambda: create_db([],[]))
        self.supervisor = MockSupervisor()
        self.supervisor.proxies = [Proxy('proxy1', 11, 'http://localhost:8080'),
                                   Proxy('proxy2', 22, 'http://localhost:8081')]
        app[app_keys.supervisor] = self.supervisor
        return app
    
    async def test_get_proxies(self):
        resp = await self.client.get(EndPoints.proxies)
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        # make sure both proxies are in the response
        self.assertIn({'id': 11, 'name': 'proxy1', 'url': 'http://localhost:8080'}, data)
        self.assertIn({'id': 22, 'name': 'proxy2', 'url': 'http://localhost:8081'}, data)
        self.assertEqual(len(data), 2)

    async def test_proxy(self):
        # get by ID
        resp = await self.client.get(EndPoints.proxy, params={'id': '11'})
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        self.assertDictEqual(data, {'id': 11, 'name': 'proxy1', 'url': 'http://localhost:8080'})

        # get by name
        resp = await self.client.get(EndPoints.proxy, params={'name': 'proxy2'})
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        self.assertDictEqual(data, {'id': 22, 'name': 'proxy2', 'url': 'http://localhost:8081'})