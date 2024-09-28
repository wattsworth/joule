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
from joule.constants import ApiErrorMessages

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
    
    async def test_get_proxy(self):

        # must specify a name or id
        resp = await self.client.get(EndPoints.proxy)
        self.assertEqual(resp.status, 400)
        self.assertIn(ApiErrorMessages.specify_id_or_path, await resp.text())

        # proxy must exist
        resp = await self.client.get(EndPoints.proxy, params={'name': 'does_not_exist'})
        self.assertEqual(resp.status, 404)
        self.assertIn("proxy does not exist", await resp.text())