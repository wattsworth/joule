import asyncio
import unittest
from unittest import mock
import logging
import signal
import psutil
import numpy as np
import shlex
import json
from typing import List
import inspect
import os
import argparse
from unittest.mock import Mock
from contextlib import contextmanager
import warnings

from joule.models import Module, Stream, Worker, Element, Supervisor
from joule.models.worker import DataConnection
from joule.models import pipes
from tests import helpers

LOG_SIZE = 10  # override module default

MODULE_LOG_AND_EXIT = os.path.join(os.path.dirname(__file__),
                                   'worker_scripts', 'log_and_exit.py')
MODULE_IGNORE_SIGTERM = os.path.join(os.path.dirname(__file__),
                                     'worker_scripts', 'ignore_sigterm.py')
MODULE_STOP_ON_SIGTERM = os.path.join(os.path.dirname(__file__),
                                      'worker_scripts', 'stop_on_sigterm.py')
MODULE_ECHO_ARGS = os.path.join(os.path.dirname(__file__),
                                'worker_scripts', 'echo_args.py')
MODULE_SIMPLE_FILTER = os.path.join(os.path.dirname(__file__),
                                    'worker_scripts', 'simple_filter.py')
warnings.simplefilter('always')

warnings.simplefilter('error')


class TestWorker(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        self.loop.set_debug(True)
        #        logging.getLogger('asyncio').setLevel(logging.DEBUG)
        asyncio.set_event_loop(self.loop)
        # generic float32_4 streams
        streams = [Stream(name="str%d" % n, datatype=Stream.DATATYPE.FLOAT32,
                          elements=[Element(name="e%d" % j, index=j,
                                            display_type=Element.DISPLAYTYPE.CONTINUOUS) for j in range(3)]) for n in
                   range(5)]  # 5th stream is not produced
        self.streams = streams

        # [producer0] --<str0>--,-------------,-<str0,str2>--[consumer0]
        #                       +---[module]--+
        # [producer1] --<str1>--`             `--<str2,str3>--[consumer1]

        self.module = Module(name="module", exec_cmd="/bin/true",
                             description="test module",
                             has_interface=False, uuid=123)
        self.module.inputs = {"input1": streams[0], "input2": streams[1]}
        self.module.outputs = {"output1": streams[2], "output2": streams[3]}
        self.module.log_size = LOG_SIZE
        self.worker = Worker(self.module)
        m_producers = [Module(name="producer1", exec_cmd="/bin/runit.sh"),
                       Module(name="producer2", exec_cmd="/bin/runit.sh")]
        m_producers[0].outputs = {"output": streams[0]}
        m_producers[1].outputs = {"output": streams[1]}
        self.producers: List[Worker] = [Worker(m) for m in m_producers]
        m_consumers = [Module(name="consumer1", exec_cmd="/bin/runit.sh"),
                       Module(name="consumer2", exec_cmd="/bin/runit.sh")]
        m_consumers[0].inputs = {"input1": streams[0], "input2": streams[2]}
        m_consumers[1].inputs = {"input1": streams[2], "input2": streams[3]}
        self.consumers: List[Worker] = [Worker(m) for m in m_consumers]
        self.supervisor = Supervisor(self.producers + self.consumers)

    def tearDown(self):
        closed = self.loop.is_closed()
        if not closed:
            self.loop.call_soon(self.loop.stop)
            self.loop.run_forever()
            self.loop.close()
        asyncio.set_event_loop(None)

    def test_builds_worker_from_module(self):
        # subscriber arrays are empty
        self.assertEqual(self.worker.subscribers, {self.streams[2]: [], self.streams[3]: []})
        # data connections are empty
        self.assertEqual(self.worker.input_connections, [])
        # output connections are empty
        self.assertEqual(self.worker.output_connections, [])

    @mock.patch('joule.models.worker.get_stream_path')
    def test_provides_module_attributes(self, mock_path: mock.Mock):
        mock_path.return_value = "/mock/path"
        self.assertEqual(self.worker.uuid, self.module.uuid)
        self.assertEqual(self.worker.name, self.module.name)
        self.assertEqual(self.worker.description, self.module.description)
        self.assertEqual(self.worker.has_interface, self.module.has_interface)
        connection = DataConnection("stub", 0, self.streams[0], pipes.Pipe())
        self.assertEqual(connection.location, "/mock/path")

    def test_generates_socket_name(self):
        self.assertIsNone(self.worker.interface_socket)
        self.assertEqual(self.worker.interface_name, "none")
        self.module.has_interface = True
        socket = self.worker.interface_socket
        name = self.worker.interface_name
        self.assertTrue(("%d" % self.module.uuid).encode('ascii') in socket)
        self.assertTrue("%d" % self.module.uuid in name)

    def test_produces_returns_true_if_worker_makes_output(self):

        # an output
        self.assertTrue(self.worker.produces(self.streams[2]))
        # an input
        self.assertFalse(self.worker.produces(self.streams[0]))
        # an unrelated stream
        s = helpers.create_stream("unrelated", "uint8_10")
        self.assertFalse(self.worker.produces(s))

    def test_spawns_child_process(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.worker.run(self.supervisor.subscribe,
                                                loop, restart=False))
        self.assertEqual(self.worker.process.returncode, 0)

    def test_restarts_child(self):
        loop = asyncio.get_event_loop()
        self.worker.RESTART_INTERVAL = 0.2

        # subscribe to the module outputs
        output1 = pipes.LocalPipe(layout=self.streams[2].layout, loop=loop)
        self.worker.subscribe(self.streams[2], output1)

        with self.check_fd_leakage():
            with self.assertLogs(logging.getLogger('joule'), logging.WARNING):
                loop.run_until_complete(asyncio.gather(
                    loop.create_task(self._stop_worker(loop)),
                    loop.create_task(self.worker.run(self.supervisor.subscribe,
                                                     loop, restart=True))
                ))
        self.assertEqual(self.worker.process.returncode, 0)
        self.assertEqual(len(output1.read_nowait()), 0)
        self.assertTrue(output1.end_of_interval)

    def test_collects_statistics(self):
        # child should listen for stop_requested flag

        loop = asyncio.get_event_loop()
        self.module.exec_cmd = "python " + MODULE_STOP_ON_SIGTERM

        async def get_statistics():
            await asyncio.sleep(0.1)
            statistics = await self.worker.statistics()
            self.assertIsNotNone(statistics.pid)
            self.assertGreater(statistics.memory_percent, 0)
            # kill the process and try to get statistics again
            os.kill(statistics.pid, signal.SIGKILL)
            await asyncio.sleep(0.1)
            null_statistics = await self.worker.statistics()
            self.assertIsNone(null_statistics.pid)
            self.assertIsNone(null_statistics.memory_percent)

        # no statistics available before worker starts
        stats = loop.run_until_complete(self.worker.statistics())
        self.assertEqual(stats.pid, None)

        with self.check_fd_leakage():
            loop.run_until_complete(asyncio.gather(
                loop.create_task(get_statistics()),
                loop.create_task(self.worker.run(self.supervisor.subscribe,
                                                 loop, restart=False))
            ))

    def test_restarts_and_stops_child_by_request(self):
        # child should listen for stop_requested flag
        loop = asyncio.get_event_loop()
        self.worker.RESTART_INTERVAL = 0.01
        self.module.exec_cmd = "python " + MODULE_STOP_ON_SIGTERM

        # calling stop before run doesn't matter
        loop.run_until_complete(self.worker.stop(loop))

        with self.assertLogs(level="WARNING") as logs:
            with self.check_fd_leakage():
                loop.run_until_complete(asyncio.gather(
                    loop.create_task(self._stop_worker(loop)),
                    loop.create_task(self._restart_worker(loop)),
                    loop.create_task(self.worker.run(self.supervisor.subscribe,
                                                     loop, restart=True))
                ))
        # check to make sure it was killed by SIGTERM
        self.assertEqual(self.worker.process.returncode, -1 * signal.SIGTERM)
        # the restart should be logged
        self.assertTrue("restarting" in ''.join(logs.output).lower())
        # make the the module started multiple times
        num_starts = 0
        for entry in self.worker.logs:
            if 'starting' in entry:
                num_starts += 1
        self.assertEqual(num_starts, 2)
        # can call stop multiple times
        loop.run_until_complete(self.worker.stop(loop))

    def test_terminates_child(self):
        # send SIGKILL to terminate bad children

        loop = asyncio.get_event_loop()
        self.module.exec_cmd = "python " + MODULE_IGNORE_SIGTERM
        # speed up the test
        self.worker.SIGTERM_TIMEOUT = 0.5
        with self.assertLogs(level="WARNING"):
            with self.check_fd_leakage():
                loop.run_until_complete(asyncio.gather(
                    loop.create_task(self._stop_worker(loop)),
                    loop.create_task(self.worker.run(self.supervisor.subscribe,
                                                     loop, restart=False))
                ))
        # check to make sure it was killed by SIGKILL
        self.assertEqual(self.worker.process.returncode, -1 * signal.SIGKILL)

    def test_builds_child_arguments(self):
        loop = asyncio.get_event_loop()
        self.module.exec_cmd = "python " + MODULE_ECHO_ARGS
        self.module.arguments = {'arg1': "value1",
                                 'arg2': "value2"}
        self.module.has_interface = True
        self.worker.log = Mock()
        loop.run_until_complete(self.worker.run(self.supervisor.subscribe,
                                                loop, restart=False))
        self.assertEqual(self.worker.process.returncode, 0)
        # expect to get a pipes argument that is a json string
        parser = argparse.ArgumentParser()
        parser.add_argument("--pipes")
        parser.add_argument("--socket")
        parser.add_argument("--arg1")
        parser.add_argument("--arg2")
        # get the second log entry which is the echo'd arguments
        argv = shlex.split(self.worker.log.mock_calls[1][1][0])
        args = parser.parse_args(argv)
        my_pipes = json.loads(args.pipes)
        socket_name = args.socket
        # verify inputs and outputs are in the config
        value = self.streams[0].to_json()
        self.assertEqual(my_pipes['inputs']['input1']['stream'], value)
        value = self.streams[1].to_json()
        self.assertEqual(my_pipes['inputs']['input2']['stream'], value)
        value = self.streams[2].to_json()
        self.assertEqual(my_pipes['outputs']['output1']['stream'], value)
        value = self.streams[3].to_json()
        self.assertEqual(my_pipes['outputs']['output2']['stream'], value)
        self.assertEqual(socket_name, self.worker.interface_name)
        self.assertEqual(args.arg1, "value1")
        self.assertEqual(args.arg2, "value2")

    def test_logs_child_output(self):
        loop = asyncio.get_event_loop()
        self.module.description = "test"
        self.module.exec_cmd = "python " + MODULE_LOG_AND_EXIT
        loop.run_until_complete(self.worker.run(self.supervisor.subscribe,
                                                loop, restart=False))
        self.assertEqual(self.worker.process.returncode, 0)
        # log should have a starting entry
        self.assertRegex(self.worker.logs[0], 'starting')
        # ...content produced by the module (just echo'd params)
        self.assertRegex(self.worker.logs[1], 'hello world')
        # ...and a terminating entry
        self.assertRegex(self.worker.logs[2], 'terminated')

    def test_inputs_must_be_available(self):
        self.module.inputs["missing_input"] = self.streams[4]
        loop = asyncio.get_event_loop()

        with self.assertLogs(level="ERROR"):
            loop.run_until_complete(self.worker.run(self.supervisor.subscribe,
                                                    loop, restart=False))
        for entry in self.worker.logs:
            if "inputs are not available" in entry:
                break
        else:
            self.fail("missing log entry")

    def test_handles_invalid_exec_cmds(self):
        self.module.exec_cmd = "bad-cmd"
        loop = asyncio.get_event_loop()
        with self.assertLogs(level="ERROR"):
            loop.run_until_complete(self.worker.run(self.supervisor.subscribe,
                                                    loop, restart=False))
        for entry in self.worker.logs:
            if "cannot start module" in entry:
                break
        else:
            self.fail("missing log entry")

    def test_rolls_logs(self):
        loop = asyncio.get_event_loop()
        self.module.exec_cmd = "/usr/bin/yes #"
        with self.check_fd_leakage():
            loop.run_until_complete(asyncio.gather(
                loop.create_task(self._stop_worker(loop)),
                loop.create_task(self.worker.run(self.supervisor.subscribe,
                                                 loop, restart=False))
            ))
        logs = self.worker.logs
        self.assertEqual(len(logs), LOG_SIZE)
        # make sure the entries have rolled
        self.assertFalse('starting' in logs[0])
        # make sure the last entry is the most recent
        self.assertTrue('terminated' in logs[-1])

    def test_passes_data_across_pipes(self):

        loop = asyncio.get_event_loop()
        # create worker connections
        # child runs until stopped
        self.module.exec_cmd = "/usr/bin/env python " + MODULE_SIMPLE_FILTER

        interval1_data = helpers.create_data('float32_3', start=1000, step=100, length=100)
        interval2_data = helpers.create_data('float32_3', start=1001+100*100, step=100, length=100)

        async def mock_producers():
            # await asyncio.sleep(0.5)
            subscribers = self.producers[0].subscribers[self.streams[0]]
            while len(subscribers) == 0:
                await asyncio.sleep(0.01)
            # add two intervals of mock data to the producer queues
            input1 = subscribers[0]#self.producers[0].subscribers[self.streams[0]][0]
            await input1.write(interval1_data)
            await input1.close_interval()
            await input1.write(interval2_data)
            await input1.close_interval()
            await input1.close()

            input2 = self.producers[1].subscribers[self.streams[1]][0]
            await input2.write(interval1_data)
            await input2.close_interval()
            await input2.write(interval2_data)
            await input2.close_interval()
            await input2.close()

            await asyncio.sleep(2)

        # subscribe to the module outputs
        output1 = pipes.LocalPipe(layout=self.streams[2].layout, loop=loop, name="output1", debug=False)
        output2 = pipes.LocalPipe(layout=self.streams[3].layout, loop=loop, name="output2", debug=False)

        # create a slow subscriber that times out
        class SlowPipe(pipes.Pipe):
            async def write(self, data):
                await asyncio.sleep(10)

            async def close_interval(self):
                pass

        slow_pipe = SlowPipe(stream=helpers.create_stream('slow stream', self.streams[2].layout))
        self.worker.subscribe(self.streams[2], slow_pipe)
        self.worker.SUBSCRIBER_TIMEOUT = 0.1

        # create a subscriber that errors out
        class ErrorPipe(pipes.Pipe):
            async def write(self, data):
                raise BrokenPipeError()

        error_pipe = ErrorPipe(stream=helpers.create_stream('error stream', self.streams[2].layout))
        self.worker.subscribe(self.streams[3], error_pipe)
        self.worker.subscribe(self.streams[3], output2)

        self.worker.subscribe(self.streams[2], output1)
        with self.assertLogs() as log:
            loop.run_until_complete(asyncio.gather(
                self.worker.run(self.supervisor.subscribe, loop, restart=False),
                mock_producers()))
        log_dump = '\n'.join(log.output)
        self.assertIn("subscriber write error", log_dump)
        self.assertIn("timed out", log_dump)
        # check stream2, should be stream0*2.0 [] stream0*2.0
        output_data = output1.read_nowait()
        output1.consume(len(output_data))
        np.testing.assert_array_almost_equal(interval1_data['data'] * 2.0,
                                             output_data['data'])
        self.assertTrue(output1.end_of_interval)
        output_data = output1.read_nowait()
        output1.consume(len(output_data))
        np.testing.assert_array_almost_equal(interval2_data['data'] * 2.0,
                                             output_data['data'])
        self.assertTrue(output1.end_of_interval)

        # check stream3, should be stream1*3.0 [] stream1*3.0
        output_data = output2.read_nowait()
        output2.consume(len(output_data))
        np.testing.assert_array_almost_equal(interval1_data['data'] * 3.0,
                                             output_data['data'])
        self.assertTrue(output2.end_of_interval)
        output_data = output2.read_nowait()
        output2.consume(len(output_data))
        np.testing.assert_array_almost_equal(interval2_data['data'] * 3.0,
                                             output_data['data'])
        self.assertTrue(output2.end_of_interval)

    async def _stop_worker(self, loop: asyncio.AbstractEventLoop, delay=0.5):
        await asyncio.sleep(delay)
        await self.worker.stop(loop)

    async def _restart_worker(self, loop: asyncio.AbstractEventLoop, delay=0.2):
        await asyncio.sleep(delay)
        await self.worker.restart(loop)

    @contextmanager
    def check_fd_leakage(self):
        self.proc = psutil.Process()
        self.orig_fds = self.proc.num_fds()
        yield
        self.assertEqual(self.proc.num_fds(), self.orig_fds)


""" from git gist """
descriptors = set()


def print_open_fds(print_all=False):
    global descriptors
    (frame, filename, line_number, function_name, lines, index) = inspect.getouterframes(inspect.currentframe())[1]
    fds = set(os.listdir('/proc/self/fd/'))
    new_fds = fds - descriptors
    closed_fds = descriptors - fds
    descriptors = fds

    if print_all:
        print("{}:{} ALL file descriptors: {}".format(filename, line_number, fds))

    if new_fds:
        print("{}:{} new file descriptors: {}".format(filename, line_number, new_fds))
    if closed_fds:
        print("{}:{} closed file descriptors: {}".format(filename, line_number, closed_fds))
