from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web
import aiohttp

from joule.models.supervisor import Supervisor
import joule.controllers
from tests.controllers.helpers import MockWorker
from joule import app_keys
from joule.constants import EndPoints

class TestModuleController(AioHTTPTestCase):

    async def get_application(self):
        app = web.Application()
        app.add_routes(joule.controllers.routes)
        wreader = MockWorker("reader", {}, {'output': '/reader/path'}, uuid=1)
        wfilter = MockWorker("filter", {'input': '/reader/path'}, {'output': '/output/path'}, uuid=2)
        app[app_keys.supervisor] = Supervisor([wreader, wfilter], [], None)  # type: ignore
        return app


    async def test_module_list(self):
        resp: aiohttp.ClientResponse = await self.client.request("GET", EndPoints.modules,
                                                                 params={"statistics": 1})
        workers = await resp.json()
        self.assertEqual(len(workers), 2)
        for worker in workers:
            if worker['name'] == 'reader':
                self.assertEqual(worker['outputs']['output'], '/reader/path')
                self.assertEqual(len(worker['inputs']), 0)
            if worker['name'] == 'filter':
                self.assertEqual(worker['outputs']['output'], '/output/path')
                self.assertEqual(worker['inputs']['input'], '/reader/path')
            self.assertIn('statistics', worker)

        # can ommit statistics in the response
        resp = await self.client.request("GET", EndPoints.modules)
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
            self.assertNotIn('statistics', worker)


    async def test_module_info(self):
        # can retrieve info by name
        resp = await self.client.request("GET", EndPoints.module,
                                         params={'name': 'filter'})
        worker = await resp.json()
        self.assertEqual(worker['outputs']['output'], '/output/path')
        self.assertEqual(worker['inputs']['input'], '/reader/path')
        self.assertIn('statistics', worker)

        # can retrieve info by ID
        resp = await self.client.request("GET", EndPoints.module,
                                         params={'id': 2})
        worker = await resp.json()
        self.assertEqual(worker['outputs']['output'], '/output/path')
        self.assertEqual(worker['inputs']['input'], '/reader/path')
        self.assertIn('statistics', worker)


    async def test_module_logs(self):
        # can retrieve logs by name
        resp = await self.client.request("GET", EndPoints.module_logs,
                                         params={'name': 'reader'})
        logs = await resp.json()
        # mock worker produces two log entries
        self.assertEqual(len(logs), 2)

        # can retrieve logs by ID
        resp = await self.client.request("GET", EndPoints.module_logs,
                                         params={'id': 2})
        logs = await resp.json()
        # mock worker produces two log entries
        self.assertEqual(len(logs), 2)
