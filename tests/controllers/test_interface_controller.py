from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
import unittest
from aiohttp import web
import argparse
import multiprocessing
import json
import asyncio
from contextlib import redirect_stdout
import io

import joule.controllers
from joule.client import FilterModule
from joule.models import Supervisor
from .helpers import MockWorker


class InterfaceModule(FilterModule):

    async def run(self, parsed_args, inputs, outputs):
        while not self.stop_requested:
            await asyncio.sleep(0.1)

    def routes(self):
        return[
            web.get('/', self.index),
            web.get('/test', self.test)
        ]

    async def index(self, request):
        return web.Response(text="index")

    async def test(self, request):
        self.stop_requested = True
        return web.Response(text="Hello World")


class TestInterfaceController(AioHTTPTestCase):

    async def get_application(self):
        app = web.Application()
        app.add_routes(joule.controllers.routes)
        socket_name= b'\x00' + 'interface.test'.encode('ascii')
        winterface = MockWorker("reader", {}, {'output': '/reader/path'},
                                uuid=101, socket=socket_name)
        app["supervisor"] = Supervisor([winterface])  # type: ignore
        return app

    @unittest_run_loop
    async def test_proxies_get_requests(self):
        # start up the module
        module = InterfaceModule()
        args = argparse.Namespace(socket='interface.test',
                                  pipes=json.dumps(json.dumps(
                                      {'inputs': {}, 'outputs': {}})))
        old_loop = asyncio.get_event_loop()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        proc = multiprocessing.Process(target=module.start, args=(args, ))
        f = io.StringIO()
        with redirect_stdout(f):
            proc.start()
        loop.close()
        asyncio.set_event_loop(old_loop)
        # passes root as / to module
        resp = await self.client.request("GET", "/interface/101")
        msg = await resp.text()
        self.assertEqual(msg, 'index')
        # another path, this one shuts down the module
        resp = await self.client.request("GET", "/interface/101/test")
        msg = await resp.text()
        proc.join()
        self.assertEqual(resp.status, 200)
        self.assertEqual("Hello World", msg)
