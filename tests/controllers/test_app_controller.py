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
        self.supervisor.workers = [MockWorker('worker1', {}, {}, 10, is_app=True),
                                   MockWorker('worker2', {}, {}, 20, is_app=False)]
        self.supervisor.proxies = [Proxy('proxy1', 11, 'http://localhost:8080'),
                                   Proxy('proxy2', 22, 'http://localhost:8081')]
        app[app_keys.supervisor] = self.supervisor
        return app
    
    async def test_get_apps(self):
        resp = await self.client.get(EndPoints.app_json)
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        # make sure the data app worker is in the response
        self.assertIn({'id': 'm10', 'name': 'worker1'}, data)
        # make suer the non-app worker is not in the response
        self.assertNotIn({'id': 'm20', 'name': 'worker2'}, data)
        # make sure both proxies are in the response
        self.assertIn({'id': 'p11', 'name': 'proxy1'}, data)
        self.assertIn({'id': 'p22', 'name': 'proxy2'}, data)

    async def test_get_app_auth(self):
        resp = await self.client.get(EndPoints.app_auth, headers={"X-App-Id": "m10"})
        self.assertEqual(resp.status, 200)
        # mock supervisor return --uuid-- for the module socket
        self.assertEqual(resp.headers['X-Proxy-Path'], "http://unix:--10--:/")

        resp = await self.client.get(EndPoints.app_auth, headers={"X-App-Id": "p11"})
        self.assertEqual(resp.status, 200)
        # mock supervisor returns the url for the proxy
        self.assertEqual(resp.headers['X-Proxy-Path'], "http://localhost:8080")