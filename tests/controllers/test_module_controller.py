from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web
import aiohttp

from joule.models.supervisor import Supervisor
import joule.controllers
from tests.controllers.helpers import MockWorker


class TestModuleController(AioHTTPTestCase):

    async def get_application(self):
        app = web.Application()
        app.add_routes(joule.controllers.routes)
        wreader = MockWorker("reader", {}, {'output': '/reader/path'})
        wfilter = MockWorker("filter", {'input': '/reader/path'}, {'output': '/output/path'})
        app["supervisor"] = Supervisor([wreader, wfilter], [], None)  # type: ignore
        return app


    async def test_module_list(self):
        resp: aiohttp.ClientResponse = await self.client.request("GET", "/modules.json?statistics=1")
        workers = await resp.json()
        # check some fields in the response
        self.assertEqual(len(workers), 2)
        for worker in workers:
            if worker['name'] == 'reader':
                self.assertEqual(worker['outputs']['output'], '/reader/path')
                self.assertEqual(len(worker['inputs']), 0)
            if worker['name'] == 'filter':
                self.assertEqual(worker['outputs']['output'], '/output/path')
                self.assertEqual(worker['inputs']['input'], '/reader/path')
            self.assertTrue('statistics' in worker)


    async def test_module_info(self):
        resp = await self.client.request("GET", "/module.json",
                                         params={'name': 'filter'})
        worker = await resp.json()
        self.assertEqual(worker['outputs']['output'], '/output/path')
        self.assertEqual(worker['inputs']['input'], '/reader/path')
        self.assertTrue('statistics' in worker)


    async def test_module_logs(self):
        resp = await self.client.request("GET", "/module/logs.json",
                                         params={'name': 'reader'})
        logs = await resp.json()
        # mock worker produces two log entries
        self.assertEqual(len(logs), 2)
