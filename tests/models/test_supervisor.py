import unittest
from joule.models import Module, Worker, Supervisor
from typing import List
import functools
import asyncio

from tests import helpers


class TestSupervisor(unittest.TestCase):
    NUM_WORKERS = 4

    def setUp(self):
        self.loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        self.loop.set_debug(True)

        self.workers: List[Worker] = []
        for x in range(TestSupervisor.NUM_WORKERS):
            module = Module(name="m%d" % x, exec_cmd="", uuid=x)
            self.workers.append(Worker(module))
        self.supervisor = Supervisor(self.workers)

    def tearDown(self):
        closed = self.loop.is_closed()
        if not closed:
            self.loop.call_soon(self.loop.stop)
            self.loop.run_forever()
            self.loop.close()
        asyncio.set_event_loop(None)

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

        self.supervisor.start(self.loop)
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
