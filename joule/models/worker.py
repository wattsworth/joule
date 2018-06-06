from sqlalchemy.orm import Session
from typing import Dict, List
import logging
import asyncio
import shlex
from joule.models.module import Module
from joule.models.stream import Stream
from joule.models.subscription import Subscription
from joule.models.errors import SubscriptionError
from joule.utils.numpypipe import (StreamNumpyPipeReader,
                                   StreamNumpyPipeWriter,
                                   EmptyPipe, fd_factory)

import os
import json

# custom types
Loop = asyncio.AbstractEventLoop
StreamQueues = Dict[Stream, List[asyncio.Queue]]

popen_lock = asyncio.Lock()


class Worker:

    def __init__(self, my_module: Module, db: Session):

        self.module: Module = my_module
        # map of output subscribers (1-many)
        self.subscribers: Dict(Stream, List[asyncio.Queue]) = {}
        # map of input subscriptions (1-1)
        self.subscriptions: Dict(Stream, Subscription) = {}

        for stream in self.module.outputs:
            # add an entry for each output
            self.subscribers[stream] = []

        for stream in self.module.inputs:
            # add an entry for each input
            self.subscriptions[stream] = None

        self.db = db
        self.process = None
        self.stop_requested = False
        self.npipes = []
        self.child_pipes = {
            'outputs': {},
            'inputs': {}
        }
        self.pipe_tasks = []

        # tunable constants
        # how long to wait for proc to stop nicely
        self.SIGTERM_TIMEOUT = 2
        # how long to wait to restart a failed process
        self.RESTART_INTERVAL = 1

    # returns a queue and unsubscribe function
    def subscribe(self, stream: Stream, loop: Loop) -> Subscription:
        q = asyncio.Queue(loop=loop)
        try:
            self.subscribers[stream].append(q)
        except KeyError:
            raise SubscriptionError()

        def unsubscribe():
            i = self.subscribers[stream].index(q)
            del self.subscribers[stream][i]

        return Subscription(q, unsubscribe)

    def register_inputs(self, workers: List['Worker'], loop: Loop) -> bool:
        # check if all the module's inputs are available
        for stream in self.subscriptions.keys():
            for worker in workers:
                try:
                    self.subscriptions[stream] = worker.subscribe(stream, loop)
                    break
                except SubscriptionError:
                    pass
            else:
                # unwind the subscriptions
                for subscription in self.input_queues.values():
                    subscription.unsubscribe()
                return False  # cannot find all input inputs
        return True

    # TODO: inserters should be built and added to the output queues:
    def _start_inserters(self, loop):
        inserter_tasks = []
        for path in self.path_workers:
            stream = self.path_streams[path]
            # build inserters for any paths that have non-zero keeps
            if (stream.keep_us):
                my_inserter = inserter.NilmDbInserter(
                    self.async_nilmdb_client,
                    path,
                    insertion_period=self.NILMDB_INSERTION_PERIOD,
                    cleanup_period=self.NILMDB_CLEANUP_PERIOD,
                    keep_us=stream.keep_us,
                    decimate=stream.decimate)
                (q, _) = self.path_workers[path]()
                coro = my_inserter.process(q, loop=loop)
                task = asyncio.ensure_future(coro)
                self.inserters.append(my_inserter)
                inserter_tasks.append(task)
        return inserter_tasks

    # ----------------------------


    async def run(self, loop: Loop, restart: bool =True):
        if not self._validate_inputs():
            return
        self.stop_requested = False
        while True:
            await self._run_once(loop)
            # only gets here if process terminates
            if restart and not self.stop_requested:
                logging.error("Restarting failed module: %s" % self.module.name)
                await asyncio.sleep(self.RESTART_INTERVAL)
                # insert an empty block in output_queues to indicate end of
                # interval
                for queues in self.subscribers.values():
                    for queue in queues:
                        queue.put_nowait(None)
            else:
                break

    def _validate_inputs(self):
        for key, value in self.subscriptions.items():
            if value is None:
                logging.error("Cannot start %s: no source for input [%s]" %
                              (self.module, key))
                return False
        return True

    async def _run_once(self, loop):
        cmd = shlex.split(self.module.exec_cmd)
        await popen_lock.acquire()
        await self._start_pipe_tasks()
        cmd += ["--pipes", json.dumps(self.child_pipes)]
        # add a socket if the module has a web interface
        if self.module.has_interface:
            self.module.socket = "/tmp/wattsworth.joule.%d" % self.module.id
            cmd += ["--socket", self.module.socket]
        # logging.warn(cmd)
        create = asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT, close_fds=False)
        try:
            self.process = await create
        except Exception as e:
            self.module.log("ERROR: cannot start module: \n\t%s" % e)
            self.module.status = Module.STATUS.FAILED
            logging.error("Cannot start [%s]" % self.module.name)
            popen_lock.release()
            self.process = None
            self._close_child_pipes()
            await self._close_npipes()
            return
        self._close_child_pipes()
        popen_lock.release()
        self.module.status = Module.STATUS.RUNNING
        self.module.pid = self.process.pid
        self.module.log("---starting module---")
        self.logger_task = asyncio.ensure_future(
            self._logger(self.process.stdout), loop=loop)

        await self.process.wait()
        self.process = None
        await self._close_npipes()

    async def stop(self, loop: Loop):
        self.stop_requested = True
        if self.process is None:
            return
        # close pipe connections with module
        await self._close_npipes()
        if self.process is None:
            return
        self.process.terminate()
        try:
            await asyncio.wait_for(self.process.wait(),
                                   timeout=self.SIGTERM_TIMEOUT,
                                   loop=loop)
        except asyncio.TimeoutError:
            logging.warning(
                "Cannot stop %s with SIGTERM, killing process" % self.module)
            self.process.kill()
        await self.logger_task

    async def _logger(self, stream):
        while True:
            bline = await stream.readline()
            if len(bline) == 0:
                break
            line = bline.decode('UTF-8').rstrip()
            self.module.log(line)

    async def _start_pipe_tasks(self):
        # configure output pipes          [module]==>[jouled]
        for pipe in self.module.outputs:
            (npipe, fd) = self._build_numpy_pipe(stream, 'output')
            self.child_pipes['outputs'][stream] = {
                'fd': pipe.fd, 'layout': stream.layout}
            self.npipes.append(npipe)
            task = asyncio.ensure_future(
                self._pipe_in(npipe, self.subscribers[stream]))
            self.pipe_tasks.append(task)

        # configure input pipes               [jouled]==>[module]
        for pipe in self.module.inputs:
            (fd, npipe) = self._build_numpy_pipe(stream, 'input')
            self.child_pipes['inputs'][stream] = {
                'fd': fd, 'layout': stream.layout}
            self.npipes.append(npipe)
            task = asyncio.ensure_future(
                self._pipe_out(self.input_queues[path], npipe))
            self.pipe_tasks.append(task)

    def _build_numpy_pipe(self, stream, direction):
        (r, w) = os.pipe()
        if (direction == 'output'):  # fd    ==> npipe
            os.set_inheritable(w, True)
            npipe = StreamNumpyPipeReader(stream.layout,
                                          reader_factory=fd_factory.reader_factory(r))

            return (npipe, w)
        else:  # npipe ==> fd
            os.set_inheritable(r, True)
            npipe = StreamNumpyPipeWriter(stream.layout,
                                          writer_factory=fd_factory.writer_factory(w))

            return (r, npipe)

    def _close_child_pipes(self):
        for pipe_set in self.child_pipes.values():
            for pipe in pipe_set.values():
                os.close(pipe['fd'])

    async def _close_npipes(self):
        for npipe in self.npipes:
            npipe.close()
        for task in self.pipe_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        # clear out the arrays
        self.npipes = []
        self.pipe_tasks = []

    async def _pipe_in(self, npipe, queues):
        """given a numpy pipe, get data and put it
           into each queue in [output_queues] """
        while (True):
            try:
                data = await npipe.read()
                npipe.consume(len(data))
                # print("adding %d rows of data to"%len(data))
                for q in queues:
                    # print("\tworker q: %d"%id(q))
                    q.put_nowait(data)
                await asyncio.sleep(0.25)
            except EmptyPipe:
                # print("empty pipe %s, exiting loop"%npipe.name)
                break

    async def _pipe_out(self, queue, npipe):
        try:
            while (True):
                data = await queue.get()
                # TODO: handle broken intervals
                if data is not None:
                    await npipe.write(data)
                # rate limit pipe reads
                await asyncio.sleep(0.25)
        except ConnectionResetError as e:
            print("reset error, for ", npipe)

    def _socket_path(id):
        path = "/tmp/joule-module-%d" % id
        try:
            os.unlink(path)
        except OSError:
            if os.path.exists(path):
                raise
