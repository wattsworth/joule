from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
import unittest
import aiohttp
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
            web.get('/test', self.get_test),
            web.post('/test_json', self.post_json),
            web.post('/test_form', self.post_form)
        ]

    async def index(self, request):
        data = request.query
        sdata = json.dumps(dict(data))
        return web.Response(text=sdata)

    async def get_test(self, request):
        self.stop_requested = True
        data = request.query
        sdata = json.dumps(dict(data))
        return web.Response(text=sdata)

    async def post_json(self, request):
        data = await request.json()
        return web.Response(text=json.dumps(data))

    async def post_form(self, request):
        self.stop_requested = True
        data = await request.post()
        return web.Response(text=json.dumps(dict(data)))


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
                                  url='http://localhost:8088',
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
        payload = {'param1': '1', 'param2': '2'}
        # passes root as / to module
        resp = await self.client.request("GET", "/interface/101?param1=1&param2=2")
        msg = await resp.text()
        self.assertEqual(payload, json.loads(msg))
        # another path, this one shuts down the module
        resp = await self.client.request("GET", "/interface/101/test?param1=1&param2=2")
        msg = await resp.text()
        proc.join()
        self.assertEqual(resp.status, 200)
        self.assertEqual(payload, json.loads(msg))

    @unittest_run_loop
    async def test_proxies_post_requests(self):
        # start up the module
        module = InterfaceModule()
        args = argparse.Namespace(socket='interface.test',
                                  url='http://localhost:8088',
                                  pipes=json.dumps(json.dumps(
                                      {'inputs': {}, 'outputs': {}})))
        old_loop = asyncio.get_event_loop()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        proc = multiprocessing.Process(target=module.start, args=(args,))
        f = io.StringIO()
        with redirect_stdout(f):
            proc.start()
        loop.close()
        asyncio.set_event_loop(old_loop)
        # POST json (preserves types)
        payload = {'param1': 1, 'param2': '2'}
        resp = await self.client.request("POST", "/interface/101/test_json", json=payload)
        msg = await resp.text()
        self.assertEqual(payload, json.loads(msg))
        # POST form data (does not preserve types)
        payload = {'param1': '1', 'param2': '2'}
        data = aiohttp.FormData()
        data.add_field('param1', '1')
        data.add_field('param2', '2')
        resp = await self.client.request("POST", "/interface/101/test_form", data=data)
        msg = await resp.text()
        self.assertEqual(payload, json.loads(msg))
        proc.join()
        self.assertEqual(resp.status, 200)
        self.assertEqual(payload, json.loads(msg))
