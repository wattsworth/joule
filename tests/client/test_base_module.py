import argparse
import asyncio
import os
import signal
import sys
import time
import threading
import tempfile
from aiohttp import web
import unittest
from unittest import mock

from joule.client import BaseModule
from tests import helpers
import warnings

warnings.simplefilter('always')


class SimpleModule(BaseModule):

    async def run_as_task(self, parsed_args, app):
        self.completed = False
        return asyncio.create_task(self.stub(parsed_args.stop_on_request))

    # generates warnings because the pipe variable is none
    def routes(self):
        return [web.get('/', self.index)]

    async def index(self, request):
        return web.Response(text="hello world")

    async def stub(self, stop_on_request):
        while True:
            if stop_on_request and self.stop_requested:
                break
            await asyncio.sleep(0.01)
        # only get here if module listens for stop request
        self.completed = True


class NetworkedModule(BaseModule):
    async def run_as_task(self, parsed_args, app):
        return asyncio.create_task(self._build_pipes(parsed_args))


class TestBaseModule(helpers.AsyncTestCase):

    def sigint(self):
        time.sleep(0.1)
        os.kill(os.getpid(), signal.SIGINT)

    # this test also checks for socket warnings if the module
    # has routes but joule doesn't provide a socket (b/c the is_app
    # flag is false in the config)
    def test_stops_on_sigint(self):
        module = SimpleModule()
        # generate a warning for the socket
        args = argparse.Namespace(socket='none', pipes='unset',
                                  api_socket='dummval', node="",
                                  url="http://localhost:8088",
                                  stop_on_request=True)
        # fire sigint
        t = threading.Thread(target=self.sigint)
        # run the module
        t.start()
        with self.assertLogs(level="ERROR") as logs:
            module.start(args)
        all_logs = '\n'.join(logs.output).lower()
        self.assertTrue('socket' in all_logs)
        asyncio.set_event_loop(self.loop)
        t.join()
        self.assertTrue(module.completed)


    # this test also checks for socket warnings if the module
    # has routes but joule doesn't provide a socket (b/c the is_app
    # flag is false in the config)
    def test_cancels_execution_if_necessary(self):
        module = SimpleModule()
        module.STOP_TIMEOUT = 0.1
        args = argparse.Namespace(socket='none',
                                  pipes='unset',
                                  api_socket='dummyval', node="",
                                  url="http://localhost:8088",
                                  stop_on_request=False)
        # fire sigint
        t = threading.Thread(target=self.sigint)
        # run the module
        t.start()
        with self.assertLogs(level="ERROR") as logs:
            module.start(args)
        all_logs = '\n'.join(logs.output).lower()
        self.assertTrue('socket' in all_logs)
        asyncio.set_event_loop(self.loop)
        t.join()
        self.assertFalse(module.completed)


    # builds network pipes if pipe arg is 'unset'
    def test_builds_network_pipes(self):
        #### THIS TESTS OLD CODE, MIGRATE TO BUILD_PIPES_NEW (still used by composite module) ####
        built_pipes = False

        async def mock_builder(inputs, outputs, streams, node, start_time, end_time, live, force):
            nonlocal built_pipes
            built_pipes = True
            self.assertEqual(len(inputs), 2)
            self.assertEqual(inputs['input1'], '/test/input1:float32[x,y,z]')
            self.assertEqual(len(outputs), 2)
            self.assertEqual(outputs['output2'], '/test/output2:float32[x,y,z]')
            return {}, {}

        module_mock = mock.Mock()
        module_mock.build_network_pipes = mock_builder
        with mock.patch.dict(sys.modules,
                             {'joule.client.helpers.pipes': module_mock}):
            with tempfile.NamedTemporaryFile() as f:
                module = NetworkedModule()
                f.write(str.encode(
                    """
                    [Main]
                    name = test
                    exec_cmd = runit.sh
                    [Arguments]
    
                    [Inputs]
                    input1 = /test/input1:float32[x,y,z]
                    input2 = /test/input2:float32[x,y,z]
    
                    [Outputs]
                    output1 = /test/output1:float32[x,y,z]
                    output2 = /test/output2:float32[x,y,z]
                    """))
                f.flush()
                # set api_socket to dummyval to prevent module from requesting
                # the node from the user configs which is not present here
                args = argparse.Namespace(socket='none', pipes='unset',
                                          api_socket='dummyval', node="",
                                          start_time='1 hour ago', end_time=None, force=True,
                                          module_config=f.name,
                                          stream_configs='unset',
                                          new=False,
                                          live=False,
                                          url='http://localhost:8088')
                module.start(args)
                self.assertTrue(built_pipes)
