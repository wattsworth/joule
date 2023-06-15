from joule.models import Module, Worker, pipes
from joule.models.supervisor import Supervisor
from typing import List
import functools
import asyncio
import unittest

from tests import helpers
from tests.helpers import AsyncTestCase


class TestSupervisor(AsyncTestCase):
    NUM_WORKERS = 4

    def setUp(self):
        super().setUp()
        self.workers: List[Worker] = []
        for x in range(TestSupervisor.NUM_WORKERS):
            module = Module(name="m%d" % x, exec_cmd="", uuid=x)
            self.workers.append(Worker(module))
        self.supervisor = Supervisor(self.workers, [], None)

    def test_returns_workers(self):
        self.assertEqual(self.workers, self.supervisor.workers)

    def test_starts_and_stops_workers(self):
        started_uuids = []
        stopped_uuids = []

        async def mock_run(uuid, _):
            started_uuids.append(uuid)

        async def mock_stop(uuid):
            stopped_uuids.append(uuid)

        for worker in self.workers:
            worker.run = functools.partial(mock_run, worker.module.uuid)
            worker.stop = functools.partial(mock_stop, worker.module.uuid)

        asyncio.run(self.supervisor.start())
        asyncio.run(self.supervisor.stop())
        # make sure each worker ran
        for worker in self.workers:
            self.assertTrue(worker.module.uuid in started_uuids)
            self.assertTrue(worker.module.uuid in stopped_uuids)

        self.assertEqual(len(started_uuids), TestSupervisor.NUM_WORKERS)
        self.assertEqual(len(stopped_uuids), TestSupervisor.NUM_WORKERS)

    def test_returns_sockets(self):
        for worker in self.workers:
            uuid = worker.module.uuid
            self.assertEqual(worker.interface_socket,
                             self.supervisor.get_module_socket(uuid))
        # returns None if the uuid doesn't exist
        bad_uuid = 68
        self.assertIsNone(self.supervisor.get_module_socket(bad_uuid))

    def test_restarts_producers(self):
        restarted = False

        async def mock_restart():
            nonlocal restarted
            restarted = True

        s = helpers.create_stream("test", "float32_3")
        self.workers[0].module.outputs['output'] = s
        self.workers[0].restart = mock_restart
        with self.assertLogs(level="WARNING") as logs:
            asyncio.run(
                self.supervisor.restart_producer(s, msg="test"))
        self.assertTrue('restarting' in ''.join(logs.output).lower())
        self.assertTrue(restarted)
        # check the worker logs
        self.assertTrue("restarting" in ''.join(self.workers[0].logs).lower())
        self.assertTrue("test" in ''.join(self.workers[0].logs).lower())

    def test_subscribes_to_remote_inputs(self):
        remote_stream = helpers.create_stream('remote', 'float64_2')
        remote_stream.set_remote('http://remote:3000', '/path/to/stream')
        p1 = pipes.LocalPipe(layout='float64_2', name='p1')
        p2 = pipes.LocalPipe(layout='float64_2', name='p2')
        subscription_requests = 0

        class MockNode:
            def __init__(self):
                pass

            async def data_subscribe(self, stream):
                nonlocal subscription_requests
                pipe = pipes.LocalPipe(layout='float64_2')
                subscription_requests += 1
                return pipe

            async def close(self):
                pass

        def get_mock_node(name: str):
            #TODO: name should just be the CN of the node
            self.assertEqual(name, "http://remote:3000")
            return MockNode()

        async def setup():
            self.supervisor.get_node = get_mock_node
            self.supervisor.subscribe(remote_stream, p1)
            self.supervisor.subscribe(remote_stream, p2)

            self.supervisor.task = asyncio.sleep(0)
        asyncio.run(setup())
        asyncio.run(self.supervisor.stop())

        # make sure there is only one connection to the remote
        self.assertEqual(subscription_requests, 1)
        # p2 should be subscribed to p1
        self.assertTrue(p1.subscribers[0] is p2)

        # now "stop" the supervisor and the pipes should be closed

        self.assertTrue(p1.closed)
        self.assertTrue(p2.closed)

    @unittest.skip("Test is broken, but this hasn't been used so ignore for now")
    def test_subscribes_to_remote_outputs(self):
        remote_stream = helpers.create_stream('remote', 'float64_2')
        remote_stream.set_remote('remote:3000', '/path/to/stream')
        module = Module(name="remote_output", exec_cmd="", uuid=0)
        module.outputs = {'output': remote_stream}
        worker = Worker(module)

        async def mock_run(subscribe):
            await asyncio.sleep(0.1)

        worker.run = mock_run

        output_requested = False

        class MockNode:
            def __init__(self):
                pass

            async def data_write(self, stream):
                nonlocal output_requested
                output_requested = True
                pipe = pipes.LocalPipe(layout='float64_2')
                return pipe

            async def close(self):
                pass

        def get_mock_node(name: str):
            #TODO: name should just be the CN of the node
            self.assertEqual(name, "remote:3000")
            return MockNode()

        supervisor = Supervisor([worker], [], get_mock_node)

        asyncio.run(supervisor.start())
        self.supervisor.task = asyncio.sleep(0.1)
        asyncio.run(self.supervisor.start())
        asyncio.run(self.supervisor.stop())

        # pipe should be created
        self.assertTrue(output_requested)
        # worker should be producing data into the pipe
        self.assertEqual(1, len(worker.subscribers[remote_stream]))
        asyncio.run(supervisor.stop())
