import asyncio
import unittest
import logging
import signal
import psutil
import numpy as np
import shlex
import json
from typing import List
import inspect, os, pdb
import argparse
from unittest.mock import Mock
from contextlib import contextmanager

from joule.models import Module, Stream, Worker, Element, Supervisor
from joule.models import pipes
from .. import helpers

LOG_SIZE = 10  # override module default


class TestWorker(unittest.TestCase):

    def setUp(self):
        # generic float32_4 streams
        streams = [Stream(name="str%d" % n, datatype=Stream.DATATYPE.FLOAT32,
                          elements=[Element(name="e%d" % j, index=j,
                                            display_type=Element.DISPLAYTYPE.CONTINUOUS) for j in range(3)]) for n in
                   range(4)]
        self.streams = streams

        # [producer0] --<str0>--,----------------<str0,str2>--[consumer0]
        #                       +---[module]--+
        # [producer1] --<str1>--`             `--<str2,str3>--[consumer1]

        self.module = Module(name="module", exec_cmd="/bin/true")
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

    def test_builds_worker_from_module(self):
        # subscriber arrays are empty
        self.assertEqual(self.worker.subscribers, {self.streams[2]: [], self.streams[3]: []})
        # data connections are empty
        self.assertEqual(self.worker.input_connections, [])
        # output connections are empty
        self.assertEqual(self.worker.output_connections, [])

    def test_spawns_child_process(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.worker.run(self.supervisor.subscribe,
                                                loop, restart=False))
        self.assertEqual(self.worker.process.returncode, 0)

    def test_restarts_child(self):
        loop = asyncio.get_event_loop()
        self.worker.RESTART_INTERVAL = 0.2

        with self.check_fd_leakage():
            with self.assertLogs(logging.getLogger('joule'), logging.WARNING):
                loop.run_until_complete(asyncio.gather(
                    loop.create_task(self._stop_worker(loop)),
                    loop.create_task(self.worker.run(self.supervisor.subscribe,
                                                     loop, restart=True))
                ))
        self.assertEqual(self.worker.process.returncode, 0)

    def test_stops_child(self):
        # yes runs forever, # ignores the parameters
        self.module.exec_cmd = "/usr/bin/yes #"
        loop = asyncio.get_event_loop()
        # self.worker.subscribe_to_inputs(self.producers, loop)
        with self.check_fd_leakage():
            loop.run_until_complete(asyncio.gather(
                loop.create_task(self._stop_worker(loop)),
                loop.create_task(self.worker.run(self.supervisor.subscribe,
                                                 loop, restart=False))
            ))
        # check to make sure it was killed by SIGTERM
        self.assertEqual(self.worker.process.returncode, -1 * signal.SIGTERM)

    def test_builds_pipes_argument(self):
        loop = asyncio.get_event_loop()
        self.module.exec_cmd = "/bin/echo"
        self.worker.log = Mock()
        loop.run_until_complete(self.worker.run(self.supervisor.subscribe,
                                                loop, restart=False))
        self.assertEqual(self.worker.process.returncode, 0)
        # expect to get a pipes argument that is a json string
        parser = argparse.ArgumentParser()
        parser.add_argument("--pipes")
        # get the second log entry which is the echo'd arguments
        argv = shlex.split(self.worker.log.mock_calls[1][1][0])
        args = parser.parse_args(argv)
        my_pipes = json.loads(args.pipes)
        # verify inputs and outputs are in the config
        value = self.streams[0].to_json()
        self.assertEqual(my_pipes['inputs']['input1']['stream'], value)
        value = self.streams[1].to_json()
        self.assertEqual(my_pipes['inputs']['input2']['stream'], value)
        value = self.streams[2].to_json()
        self.assertEqual(my_pipes['outputs']['output1']['stream'], value)
        value = self.streams[3].to_json()
        self.assertEqual(my_pipes['outputs']['output2']['stream'], value)

    def test_logs_child_output(self):
        loop = asyncio.get_event_loop()
        self.module.exec_cmd = "/bin/echo"
        loop.run_until_complete(self.worker.run(self.supervisor.subscribe,
                                                loop, restart=False))
        self.assertEqual(self.worker.process.returncode, 0)
        # log should have a starting entry
        self.assertRegex(self.worker.logs[0], 'starting')
        # ...content produced by the module (just echo'd params)
        self.assertRegex(self.worker.logs[1], 'pipes')
        # ...and a terminating entry
        self.assertRegex(self.worker.logs[2], 'terminated')

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
        all_workers = [self.worker, *self.producers, *self.consumers]
        # child runs until stopped
        self.module.exec_cmd = "/usr/bin/yes #"

        async def mock_child():
            # wait until the worker has "started" the child
            await asyncio.sleep(0.5)
            # create pipes from fd's
            inputs = []
            for c in self.worker.input_connections:
                rf = pipes.reader_factory(c.child_fd, loop)
                inputs.append(pipes.InputPipe(name=c.name,
                                              stream=c.stream,
                                              reader_factory=rf))
            outputs = []
            for c in self.worker.output_connections:
                wf = pipes.writer_factory(c.child_fd, loop)
                outputs.append(pipes.OutputPipe(name=c.name,
                                                stream=c.stream,
                                                writer_factory=wf))

            # read input1 and send it to output1
            await outputs[0].write(await inputs[0].read(flatten=True) * 2.0)
            # read input2 and send it to output2
            await outputs[1].write(await inputs[1].read(flatten=True) * 3.0)

        input_data = helpers.create_data('float32_3')

        async def mock_producers():
            await asyncio.sleep(0.5)

            # add mock data in the producer queues
            await self.producers[0].subscribers[self.streams[0]][0].write(input_data)
            await self.producers[1].subscribers[self.streams[1]][0].write(input_data)

        # stub the close functions so the pipes stay open
        self.worker._close_child_fds = Mock()

        # subscribe to the module outputs
        output1 = pipes.LocalPipe(layout=self.streams[2].layout, loop=loop)
        output2 = pipes.LocalPipe(layout=self.streams[3].layout, loop=loop)
        self.worker.subscribe(self.streams[2], output1)
        self.worker.subscribe(self.streams[3], output2)
        loop.run_until_complete(asyncio.gather(
            self.worker.run(self.supervisor.subscribe, loop, restart=False),
            mock_child(), mock_producers(),
            self._stop_worker(loop)))
        # check stream2, should be stream0*2.0
        data = output1.read_nowait()
        np.testing.assert_array_almost_equal(input_data['data'] * 2.0, data['data'])
        # check stream3, should be stream1*3.0
        data = output2.read_nowait()
        np.testing.assert_array_almost_equal(input_data['data'] * 3.0, data['data'])

    async def _stop_worker(self, loop: asyncio.AbstractEventLoop):
        await asyncio.sleep(1)
        await self.worker.stop(loop)

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
