import argparse
import asyncio
import os
import signal
import time
import threading
from aiohttp import web

from joule.client import BaseModule
from tests import helpers
import warnings

warnings.simplefilter('always')


class SimpleModule(BaseModule):

    def run_as_task(self, parsed_args, loop):
        self.completed = False
        return asyncio.ensure_future(self.stub(parsed_args.stop_on_request))

    # generates warnings because the pipe variable is none
    def routes(self):
        return[web.get('/', self.index)]

    async def index(self, request):
        return web.Response(text="hello world")

    async def stub(self, stop_on_request):
        while True:
            if stop_on_request and self.stop_requested:
                break
            await asyncio.sleep(0.01)
        # only get here if module listens for stop request
        self.completed = True


class TestBaseModule(helpers.AsyncTestCase):

    def sigint(self):
        time.sleep(0.1)
        os.kill(os.getpid(), signal.SIGINT)

    # this test also checks for socket warnings if the module
    # has routes but joule doesn't provide a socket (b/c the has_interface
    # flag is false in the config)
    def test_stops_on_sigint(self):
        module = SimpleModule()
        # generate a warning for the socket
        args = argparse.Namespace(socket='none', pipes='unset', stop_on_request=True)
        # fire sigint
        t = threading.Thread(target=self.sigint)
        # run the module
        loop = asyncio.new_event_loop()
        loop.set_debug(True)
        asyncio.set_event_loop(loop)
        t.start()
        with self.assertLogs(level="ERROR") as logs:
            module.start(args)
        all_logs = '\n'.join(logs.output).lower()
        self.assertTrue('socket' in all_logs)
        asyncio.set_event_loop(self.loop)
        t.join()
        self.assertTrue(module.completed)

    # this test also checks for socket warnings if the module
    # has routes but joule doesn't provide a socket (b/c the has_interface
    # flag is false in the config)
    def test_cancels_execution_if_necessary(self):
        module = SimpleModule()
        module.STOP_TIMEOUT = 0.1
        args = argparse.Namespace(socket='none', pipes='unset', stop_on_request=False)
        # fire sigint
        t = threading.Thread(target=self.sigint)
        # run the module
        loop = asyncio.new_event_loop()
        loop.set_debug(True)
        asyncio.set_event_loop(loop)
        t.start()
        with self.assertLogs(level="ERROR") as logs:
            module.start(args)
        all_logs = '\n'.join(logs.output).lower()
        self.assertTrue('socket' in all_logs)
        asyncio.set_event_loop(self.loop)
        t.join()
        self.assertFalse(module.completed)


