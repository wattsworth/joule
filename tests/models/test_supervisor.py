
from joule.models import Module, Worker, Supervisor, pipes
from typing import List
import functools
import asyncio
from unittest import mock

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
        self.supervisor = Supervisor(self.workers)

    def test_returns_workers(self):
        self.assertEqual(self.workers, self.supervisor.workers)

    def test_starts_and_stops_workers(self):
        started_uuids = []
        stopped_uuids = []

        async def mock_run(uuid, _, loop):
            started_uuids.append(uuid)
            self.assertEqual(loop, self.loop)

        async def mock_stop(uuid, loop):
            stopped_uuids.append(uuid)
            self.assertEqual(loop, self.loop)

        for worker in self.workers:
            worker.run = functools.partial(mock_run, worker.module.uuid)
            worker.stop = functools.partial(mock_stop, worker.module.uuid)

        self.loop.run_until_complete(self.supervisor.start(self.loop))
        self.loop.run_until_complete(self.supervisor.stop(self.loop))
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
                             self.supervisor.get_socket(uuid))
        # returns None if the uuid doesn't exist
        bad_uuid = 68
        self.assertIsNone(self.supervisor.get_socket(bad_uuid))

    def test_restarts_producers(self):
        restarted = False

        async def mock_restart(_):
            nonlocal restarted
            restarted = True

        s = helpers.create_stream("test", "float32_3")
        self.workers[0].module.outputs['output'] = s
        self.workers[0].restart = mock_restart
        with self.assertLogs(level="WARNING") as logs:
            self.loop.run_until_complete(
                self.supervisor.restart_producer(s, self.loop, msg="test"))
        self.assertTrue('restarting' in ''.join(logs.output).lower())
        self.assertTrue(restarted)
        # check the worker logs
        self.assertTrue("restarting" in ''.join(self.workers[0].logs).lower())
        self.assertTrue("test" in ''.join(self.workers[0].logs).lower())

    def test_subscribes_to_remote_inputs(self):
        remote_stream = helpers.create_stream('remote', 'float64_2')
        remote_stream.set_remote('remote:3000', '/path/to/stream')
        p1 = pipes.LocalPipe(layout='float64_2', name='p1')
        p2 = pipes.LocalPipe(layout='float64_2', name='p2')
        subscription_requests = 0

        def mock_input_request(path, stream, url, pipe, loop):
            nonlocal subscription_requests
            self.assertEqual(pipe.name, 'p1')
            subscription_requests += 1

        with mock.patch('joule.models.supervisor.request_network_input',
                        mock_input_request):
            self.supervisor.subscribe(remote_stream, p1, self.loop)
            self.supervisor.subscribe(remote_stream, p2, self.loop)

        # make sure there is only one connection to the remote
        self.assertEqual(subscription_requests, 1)
        # p2 should be subscribed to p1
        self.assertTrue(p1.subscribers[0] is p2)

        # now "stop" the supervisor and the pipes should be closed
        self.supervisor.task = asyncio.sleep(0)
        self.loop.run_until_complete(self.supervisor.stop(self.loop))
        self.assertTrue(p1.closed)
        self.assertTrue(p2.closed)

    def test_subscribes_to_remote_outputs(self):
        pass
