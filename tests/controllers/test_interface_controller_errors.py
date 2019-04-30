from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web

import joule.controllers
from joule.models.supervisor import Supervisor
from tests.controllers.helpers import MockWorker


class TestInterfaceController(AioHTTPTestCase):

    async def get_application(self):
        app = web.Application()
        app.add_routes(joule.controllers.routes)
        winterface = MockWorker("reader", {}, {'output': '/reader/path'},
                                uuid=101, socket=None)
        app["supervisor"] = Supervisor([winterface], [])  # type: ignore
        return app

    @unittest_run_loop
    async def test_errors_on_invalid_module_id(self):

        # invalid id (not an int)
        resp: web.Response = await self.client.request("GET", "/interface/badval/test")
        self.assertEqual(400, resp.status)
        self.assertTrue('invalid' in await resp.text())

        # unknown module id
        resp: web.Response = await self.client.request("GET", "/interface/m57889/test")
        self.assertEqual(404, resp.status)
        self.assertTrue('not found' in await resp.text())

        # module does not have an interface
        resp: web.Response = await self.client.request("GET", "/interface/m101/test")
        self.assertEqual(404, resp.status)
        self.assertTrue('not found' in await resp.text())



