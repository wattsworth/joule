from joule.models import Module, Stream, Worker, Element
import asyncio
import unittest
import logging
import signal
import psutil
from contextlib import contextmanager


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
        self.worker = Worker(self.module)
        m_producers = [Module(name="producer1", exec_cmd="/bin/runit.sh"),
                       Module(name="producer2", exec_cmd="/bin/runit.sh")]
        m_producers[0].outputs = {"output": streams[0]}
        m_producers[1].outputs = {"output": streams[1]}
        self.producers = [Worker(m) for m in m_producers]
        m_consumers = [Module(name="consumer1", exec_cmd="/bin/runit.sh"),
                       Module(name="consumer2", exec_cmd="/bin/runit.sh")]
        m_consumers[0].inputs = {"input1": streams[0], "input2": streams[2]}
        m_consumers[1].inputs = {"input1": streams[2], "input2": streams[3]}
        self.consumers = [Worker(m) for m in m_consumers]

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
        self.assertFalse(self.consumers[0].subscribe_to_inputs([self.producers[0]], None))
        # the tentative subscription should be cancelled
        self.assertEqual(len(self.producers[0].subscribers[self.streams[0]]), 0)

    def test_spawns_child_process(self):
        loop = asyncio.get_event_loop()
        self.worker.subscribe_to_inputs(self.producers, loop)
        loop.run_until_complete(self.worker.run(loop, restart=False))
        self.assertEqual(self.worker.process.returncode, 0)

    def test_restarts_child(self):
        loop = asyncio.get_event_loop()
        self.worker.RESTART_INTERVAL=0.2
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

    async def _stop_worker(self, loop: asyncio.AbstractEventLoop):
        await asyncio.sleep(1)
        await self.worker.stop(loop)

    @contextmanager
    def check_fd_leakage(self):
        self.proc = psutil.Process()
        self.orig_fds = self.proc.num_fds()
        yield
        self.assertEqual(self.proc.num_fds(),self.orig_fds)

""" from git gist
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
"""
