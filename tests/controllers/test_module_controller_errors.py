from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web
import aiohttp

import joule.controllers
from joule.models.supervisor import Supervisor
from tests.controllers.helpers import MockWorker


class TestModuleControllerErrors(AioHTTPTestCase):

    async def get_application(self):
        app = web.Application()
        app.add_routes(joule.controllers.routes)
        wreader = MockWorker("reader", {}, {'output': '/reader/path'})
        wfilter = MockWorker("filter", {'input': '/reader/path'}, {'output': '/output/path'})
        app["supervisor"] = Supervisor([wreader, wfilter], [], None)  # type: ignore
        return app


    async def test_module_info(self):
        # must specify a name
        resp: aiohttp.ClientResponse = await self.client.request("GET", "/module.json")
        self.assertEqual(resp.status, 400)
        # return "not found" on bad name
        resp: aiohttp.ClientResponse = await self.client.request("GET", "/module.json",
                                                                 params={'name': 'unknown'})
        self.assertEqual(resp.status, 404)


    async def test_module_logs(self):
        # must specify a name
        resp: aiohttp.ClientResponse = await self.client.request("GET", "/module/logs.json")
        self.assertEqual(resp.status, 400)
        # return "not found" on bad name
        resp: aiohttp.ClientResponse = await self.client.request("GET", "/module/logs.json",
                                                                 params={'name': 'unknown'})
        self.assertEqual(resp.status, 404)
