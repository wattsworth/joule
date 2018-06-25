
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

from joule.models import Module, Stream, Worker, Element
from joule.models import pipes
from .. import helpers

LOG_SIZE = 10 # override module default


class TestWorker(unittest.TestCase):

    def setUp(self):
        # generic float32_4 streams
        streams = [Stream(name="str%d" % n, datatype=Stream.DATATYPE.FLOAT32,
                          elements=[Element(name="e%d" % j) for j in range(3)]) for n in range(4)]
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

    def test_builds_worker_from_module(self):
        # subscriber arrays are empty
        self.assertEqual(self.worker.subscribers, {self.streams[2]: [], self.streams[3]: []})
        # subscriptions are empty
        self.assertEqual(self.worker.subscriptions, {self.streams[0]: None, self.streams[1]: None})
        # input connections are empty
        self.assertEqual(self.worker.input_connections, {"input1": None, "input2": None})
        # output connections are empty
        self.assertEqual(self.worker.output_connections, {"output1": None, "output2": None})

    def test_subscribes_to_inputs(self):
        # consumers can't subscribe when inputs are not available
        for w in [self.worker, *self.consumers]:
            self.assertFalse(w.subscribe_to_inputs([], None))  # loop not needed
        # producers can subscribe because they have no inputs
        for w in self.producers:
            self.assertTrue(w.subscribe_to_inputs([], None))  # loop not needed
        # all module can subscribe when inputs are available
        all_workers = [self.worker, *self.producers, *self.consumers]
        for w in all_workers:
            self.assertTrue(w.subscribe_to_inputs(all_workers, None))  # loop not needed
        # now the workers should be linked subscribers==(queue)==>subscription
        # p0->w (stream0)
        self.assertEqual(self.producers[0].subscribers[self.streams[0]][0],
                         self.worker.subscriptions[self.streams[0]].queue)
        # p1->w (stream1)
        self.assertEqual(self.producers[1].subscribers[self.streams[1]][0],
                         self.worker.subscriptions[self.streams[1]].queue)
        # p0->c0 (stream0)
        self.assertEqual(self.producers[0].subscribers[self.streams[0]][1],
                         self.consumers[0].subscriptions[self.streams[0]].queue)
        # w->c0 (stream2)
        self.assertEqual(self.worker.subscribers[self.streams[2]][0],
                         self.consumers[0].subscriptions[self.streams[2]].queue)
        # w->c1 (stream2,stream3)
        self.assertEqual(self.worker.subscribers[self.streams[2]][1],
                         self.consumers[1].subscriptions[self.streams[2]].queue)
        self.assertEqual(self.worker.subscribers[self.streams[3]][0],
                         self.consumers[1].subscriptions[self.streams[3]].queue)

    def test_unwinds_subscriptions_when_inputs_are_not_available(self):
        # consumer0 requires producer0 and worker so subscribe_to_inputs fails
        self.assertFalse(self.consumers[0].subscribe_to_inputs([self.producers[0]], None))  # loop not needed
        # the tentative subscription should be cancelled
        self.assertEqual(len(self.producers[0].subscribers[self.streams[0]]), 0)

    def test_spawns_child_process(self):
        loop = asyncio.get_event_loop()
        self.worker.subscribe_to_inputs(self.producers, loop)
        loop.run_until_complete(self.worker.run(loop, restart=False))
        self.assertEqual(self.worker.process.returncode, 0)

    def test_restarts_child(self):
        loop = asyncio.get_event_loop()
        self.worker.RESTART_INTERVAL = 0.2
        self.worker.subscribe_to_inputs(self.producers, loop)

        with self.check_fd_leakage():
            with self.assertLogs(logging.getLogger('joule'), logging.WARNING):
                loop.run_until_complete(asyncio.gather(
                    loop.create_task(self._stop_worker(loop)),
                    loop.create_task(self.worker.run(loop, restart=True))
                ))
        self.assertEqual(self.worker.process.returncode, 0)

    def test_stops_child(self):
        # yes runs forever, # ignores the parameters
        self.module.exec_cmd = "/usr/bin/yes #"
        loop = asyncio.get_event_loop()
        self.worker.subscribe_to_inputs(self.producers, loop)
        with self.check_fd_leakage():
            loop.run_until_complete(asyncio.gather(
                loop.create_task(self._stop_worker(loop)),
                loop.create_task(self.worker.run(loop, restart=False))
            ))
        # check to make sure it was killed by SIGTERM
        self.assertEqual(self.worker.process.returncode, -1 * signal.SIGTERM)

    def test_builds_pipes_argument(self):
        loop = asyncio.get_event_loop()
        self.worker.subscribe_to_inputs(self.producers, loop)
        self.module.exec_cmd = "/bin/echo"
        self.worker.log = Mock()
        loop.run_until_complete(self.worker.run(loop, restart=False))
        self.assertEqual(self.worker.process.returncode, 0)
        # expect to get a pipes argument that is a json string
        parser = argparse.ArgumentParser()
        parser.add_argument("--pipes")
        # get the second log entry which is the echo'd arguments
        argv = shlex.split(self.worker.log.mock_calls[1][1][0])
        args = parser.parse_args(argv)
        my_pipes = json.loads(args.pipes)
        # verify inputs and outputs are in the config
        self.assertEqual(my_pipes['outputs']['output1']['layout'], 'float32_3')
        self.assertEqual(my_pipes['outputs']['output2']['layout'], 'float32_3')
        self.assertEqual(my_pipes['inputs']['input1']['layout'], 'float32_3')
        self.assertEqual(my_pipes['inputs']['input2']['layout'], 'float32_3')

    def test_logs_child_output(self):
        loop = asyncio.get_event_loop()
        self.worker.subscribe_to_inputs(self.producers, loop)
        self.module.exec_cmd = "/bin/echo"
        loop.run_until_complete(self.worker.run(loop, restart=False))
        self.assertEqual(self.worker.process.returncode, 0)
        # log should have a starting entry
        self.assertRegex(self.worker.logs[0], 'starting')
        # ...content produced by the module (just echo'd params)
        self.assertRegex(self.worker.logs[1], 'pipes')
        # ...and a terminating entry
        self.assertRegex(self.worker.logs[2], 'terminated')

    def test_rolls_logs(self):
        loop = asyncio.get_event_loop()
        self.worker.subscribe_to_inputs(self.producers, loop)
        self.module.exec_cmd = "/usr/bin/yes #"
        with self.check_fd_leakage():
            loop.run_until_complete(asyncio.gather(
                loop.create_task(self._stop_worker(loop)),
                loop.create_task(self.worker.run(loop, restart=False))
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
        for w in all_workers:
            self.assertTrue(w.subscribe_to_inputs(all_workers, loop))
        # child runs until stopped
        self.module.exec_cmd = "/usr/bin/yes #"

        async def mock_child():
            # wait until the worker has "started" the child
            await asyncio.sleep(0.5)
            # retrieve fd's
            fd_in1 = self.worker.input_connections["input1"][0]
            fd_in2 = self.worker.input_connections["input2"][0]
            fd_out1 = self.worker.output_connections["output1"][0]
            fd_out2 = self.worker.output_connections["output2"][0]
            # create pipes from fd's
            input1 = pipes.InputPipe("input1", layout=self.streams[0].layout,
                                     reader_factory=pipes.reader_factory(fd_in1, loop))
            input2 = pipes.InputPipe("input2", layout=self.streams[1].layout,
                                     reader_factory=pipes.reader_factory(fd_in2, loop))
            output1 = pipes.OutputPipe("output1", layout=self.streams[2].layout,
                                       writer_factory=pipes.writer_factory(fd_out1, loop))
            output2 = pipes.OutputPipe("output1", layout=self.streams[3].layout,
                                       writer_factory=pipes.writer_factory(fd_out2, loop))
            # read input1 and send it to output1
            await output1.write(await input1.read(flatten=True)*2.0)
            # read input2 and send it to output2
            await output2.write(await input2.read(flatten=True)*3.0)

        # stub the close functions so the pipes stay open
        self.worker._close_child_fds = Mock()
        # add mock data in the producer queues
        input_data = helpers.create_data('float32_3')
        self.producers[0].subscribers[self.streams[0]][0].put_nowait(input_data)
        self.producers[1].subscribers[self.streams[1]][0].put_nowait(input_data)

        loop.run_until_complete(asyncio.gather(
                                    self.worker.run(loop, restart=False),
                                    mock_child(),
                                    self._stop_worker(loop)))
        # check stream2, should be stream0*2.0
        data = self.consumers[0].subscriptions[self.streams[2]].queue.get_nowait()
        np.testing.assert_array_almost_equal(input_data['data']*2.0, data['data'])
        # check stream3, should be stream1*3.0
        data = self.consumers[1].subscriptions[self.streams[3]].queue.get_nowait()
        np.testing.assert_array_almost_equal(input_data['data']*3.0, data['data'])

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
