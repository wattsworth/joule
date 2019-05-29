from typing import Dict, List, Callable
import logging
import asyncio
import shlex
import os
import json
import collections
import datetime
import psutil
import numpy as np

from joule.models.module import Module
from joule.models.stream import Stream
from joule.models.folder import get_stream_path
from joule.errors import SubscriptionError
from joule.models import pipes
from joule.models.pipes.errors import EmptyPipe, PipeError

# custom types
Loop = asyncio.AbstractEventLoop
Subscribers = Dict[Stream, List[pipes.Pipe]]

popen_lock = None
log = logging.getLogger('joule')

SOCKET_BASE = "/tmp/joule/module%d"
API_SOCKET = "/tmp/joule/api"


def _initialize_popen_lock():
    global popen_lock
    if popen_lock is None:
        popen_lock = asyncio.Lock()


class DataConnection:
    def __init__(self, name: str, child_fd: int,
                 stream: Stream, pipe: pipes.Pipe,
                 unsubscribe: Callable = None):
        self.name = name
        self.child_fd = child_fd
        self.stream = stream
        self.pipe = pipe
        self.unsubscribe = unsubscribe

    @property
    def location(self):
        return get_stream_path(self.stream)

    async def disconnect(self):
        if self.unsubscribe is not None:
            self.unsubscribe()
        await self.pipe.close()


class Statistics:
    def __init__(self, pid, create_time, cpu_percent, memory_percent):
        self.pid = pid
        self.create_time = create_time
        self.cpu_percent = cpu_percent
        self.memory_percent = memory_percent

    def to_json(self):
        return {
            'pid': self.pid,
            'create_time': self.create_time,
            'cpu_percent': self.cpu_percent,
            'memory_percent': self.memory_percent
        }


class Worker:

    def __init__(self, my_module: Module):

        self.module: Module = my_module
        # map of subscribers (1-many) that consume module outputs
        self.subscribers: Subscribers = {}
        # map of (fd,pipe) connections to module input names
        self.input_connections: List[DataConnection] = []
        # map of (fd,pipe) connections to module output names
        self.output_connections: List[DataConnection] = []

        for (name, stream) in self.module.outputs.items():
            # add a subscriber array and an empty output connection
            self.subscribers[stream] = []

        self._logs = collections.deque([], maxlen=my_module.log_size)
        self.process: asyncio.subprocess.Process = None
        self.stop_requested = False

        # tunable constants
        # how long to wait for proc to stop nicely
        self.SIGTERM_TIMEOUT = 2
        # how long to wait to restart a failed process
        self.RESTART_INTERVAL = 3
        # how to wait for a subscriber to accept data
        self.SUBSCRIBER_TIMEOUT = 1
        # how long to try restarting if worker is currently missing inputs
        self.RESTART_AFTER_MISSING_INPUTS = 5

    async def statistics(self) -> Statistics:
        # gather process statistics
        try:
            if self.process is not None:
                p = psutil.Process(pid=self.process.pid)
                # collect cpu usage over a 0.5 second interval
                p.cpu_percent()
                await asyncio.sleep(0.5)
                with p.oneshot():
                    return Statistics(p.pid,
                                      p.create_time(),
                                      p.cpu_percent(),
                                      p.memory_percent())
            else:
                # worker is not running, no statistics available
                return Statistics(None, None, None, None)

        except psutil.NoSuchProcess:
            return Statistics(None, None, None, None)

    # provide the module attributes
    @property
    def uuid(self):
        return self.module.uuid

    @property
    def name(self):
        return self.module.name

    @property
    def description(self):
        return self.module.description

    @property
    def is_app(self):
        return self.module.is_app

    @property
    def interface_socket(self):
        if self.module.is_app:
            return SOCKET_BASE % self.module.uuid
        return None

    @property
    def interface_name(self):
        if self.module.is_app:
            return SOCKET_BASE % self.module.uuid
        return "none"

    def produces(self, stream: Stream) -> bool:
        # returns True if this worker produces [stream]
        for output in self.module.outputs.values():
            if output == stream:
                return True
        else:
            return False

    async def run(self, subscribe: Callable[[Stream, pipes.Pipe, Loop], Callable],
                  loop: Loop, restart: bool = True) -> None:
        self.stop_requested = False
        while True:
            # when jouled is run from the command line Ctrl+C sends SIGTERM
            # to the child and jouled which can cause jouled to restart the
            # child and then kill it
            if self.stop_requested:
                break  # pragma: no cover
            self.log("---starting module---")
            try:
                await self._spawn_child(subscribe, loop)
            except SubscriptionError as e:
                log.error("Cannot start module [%s]: %s" % (self.module.name, e))
                self.log("inputs are not available: %s" % e)
                break
            self.log("---module terminated---")
            if restart:
                await asyncio.sleep(self.RESTART_INTERVAL)
                if self.stop_requested:
                    break
                log.error("Restarting failed module: %s" % self.module.name)
                # insert an empty block in output_queues to indicate end of
                # interval
                for subscriber in self.subscribers.values():
                    for pipe in subscriber:
                        pipe.close_interval_nowait()

            else:
                break

    async def restart(self, loop: Loop) -> None:
        await self._stop_child(loop)

    async def stop(self, loop: Loop) -> None:
        self.stop_requested = True
        await self._stop_child(loop)

    async def _stop_child(self, loop: Loop) -> None:
        if self.process is None:
            return
        try:
            self.process.terminate()
        except ProcessLookupError:
            return  # process is already terminated
        try:
            await asyncio.wait_for(self.process.wait(),
                                   timeout=self.SIGTERM_TIMEOUT,
                                   loop=loop)
        except asyncio.TimeoutError:
            log.warning(
                "Cannot stop %s with SIGTERM, killing process" % self.module.name)
            try:
                self.process.kill()
            except ProcessLookupError:  # pragma: no cover
                pass  # if the process stopped after the timeout

    def log(self, msg):
        timestamp = datetime.datetime.now().isoformat()
        self._logs.append("[%s]: %s" % (timestamp, msg))
        # print("[%s: %s] " % (self.module.name, pid) + msg)

    @property
    def logs(self) -> List[str]:
        return list(self._logs)

    # returns a queue and unsubscribe function
    def subscribe(self, stream: Stream, pipe: pipes.Pipe) -> Callable:
        try:
            self.subscribers[stream].append(pipe)
        except KeyError:
            raise SubscriptionError()

        def unsubscribe():
            try:
                i = self.subscribers[stream].index(pipe)
                del self.subscribers[stream][i]
            except ValueError:
                # subscription already cancelled
                # this can happen if the _output_handler removes the subscriber
                pass

        return unsubscribe

    async def _spawn_child(self, subscribe: Callable[[Stream, pipes.Pipe, Loop], Callable],
                           loop: Loop) -> None:

        # lock so fd's don't pollute other modules
        _initialize_popen_lock()
        await popen_lock.acquire()
        try:

            await self._subscribe_to_inputs(subscribe, loop)
        except SubscriptionError as e:
            self._close_child_fds()
            popen_lock.release()
            await self._close_connections()
            raise e  # bubble up the exception

        output_task = await self._spawn_outputs(loop)
        cmd = self._compose_cmd()
        env = {**os.environ, 'PYTHONUNBUFFERED': '1'}
        create = asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env, close_fds=False)
        try:
            self.process = await create
        except Exception as e:
            self.process = None
            self.log("ERROR: cannot start module: \n\t%s" % e)
            self.module.status = Module.STATUS.FAILED
            log.error("Cannot start [%s]: %s" % (self.module.name, e))

            self._close_child_fds()
            popen_lock.release()
            await self._close_connections()
            output_task.cancel()
            try:
                await output_task
            # should be caught but on fast fails they can bubble up
            except asyncio.CancelledError:  # pragma: no cover
                pass
            return
        self._close_child_fds()
        popen_lock.release()

        logger_task = loop.create_task(self._logger())
        await self.process.wait()
        # Unwind the tasks
        await self._close_connections()
        output_task.cancel()
        logger_task.cancel()
        # collect any errors
        try:
            await output_task
            await logger_task
        # should be caught but on fast fails they can bubble up
        except asyncio.CancelledError:  # pragma: no cover
            pass

    async def _logger(self):
        try:
            stream = self.process.stdout
            while True:
                bline = await stream.readline()
                if len(bline) == 0:
                    break
                line = bline.decode('UTF-8').rstrip()
                self.log(line)
        except asyncio.CancelledError:  # pragma: no cover
            return

    async def _spawn_outputs(self, loop: Loop) -> asyncio.Task:
        tasks: List[asyncio.Task] = []
        # configure output pipes          [module]==>[worker]
        for (name, stream) in self.module.outputs.items():
            (r, w) = os.pipe()
            rf = pipes.reader_factory(r, loop)
            os.set_inheritable(w, True)
            pipe = pipes.InputPipe(name=name, stream=stream,
                                   reader_factory=rf)
            self.output_connections.append(DataConnection(
                name, w, stream, pipe))
            tasks.append(loop.create_task(
                self._output_handler(pipe, self.subscribers[stream], loop)))

        return asyncio.gather(*tasks)

    async def _output_handler(self, child_output: pipes.Pipe,
                              subscribers: List[pipes.Pipe], loop: Loop):
        """given a numpy pipe, get data and put it
           into each queue in [output_queues] """
        last_ts = None
        try:
            while True:
                data = await child_output.read()
                if len(data) > 0:

                    if not self._verify_monotonic_timestamps(data, last_ts, child_output.name):
                        for pipe in subscribers:
                            await pipe.close_interval()
                        await self.restart(loop)
                        break
                    last_ts = data['timestamp'][-1]

                    child_output.consume(len(data))
                    for pipe in subscribers[:]:
                        # if child_output.name=='output2':
                        #    print("writing to %d subscribers" % len(subscribers))
                        try:

                            await asyncio.wait_for(pipe.write(data),
                                                   self.SUBSCRIBER_TIMEOUT)
                        except (ConnectionResetError, BrokenPipeError):
                            log.warning("subscriber write error [%s] " % pipe.stream)
                            subscribers.remove(pipe)
                        except asyncio.TimeoutError:
                            log.warning("subscriber [%s] timed out" % pipe.stream)
                            pipe.close_interval_nowait()
                if child_output.end_of_interval:
                    for pipe in subscribers:
                        pipe.close_interval_nowait()

        except (EmptyPipe, asyncio.CancelledError):
            pass
        except PipeError as e:
            if 'closed pipe' in str(e):
                # during shutdown the pipe may be closed but
                # another read might be attempted by the output_handler
                pass
            else:
                log.warning("Worker %s, pipe %s: %s" % (
                    self.name, child_output.name, str(e)))

    async def _subscribe_to_inputs(self,
                                   subscribe: Callable[[Stream, pipes.Pipe, Loop], Callable],
                                   loop: Loop):
        # configure input pipes            [module]<==[worker]
        for (name, stream) in self.module.inputs.items():
            (r, w) = os.pipe()
            wf = pipes.writer_factory(w, loop)
            writer = await wf()
            os.set_inheritable(r, True)
            pipe = pipes.OutputPipe(name=name, stream=stream,
                                    writer=writer)
            try:
                unsubscribe = subscribe(stream, pipe, loop)
            except SubscriptionError as e:
                os.close(r)
                await pipe.close()
                raise e  # bubble exception up
            self.input_connections.append(DataConnection(name,
                                                         r, stream,
                                                         pipe,
                                                         unsubscribe))

    def _compose_cmd(self) -> str:
        cmd = shlex.split(self.module.exec_cmd)
        output_args = {}
        for c in self.output_connections:
            output_args[c.name] = {'fd': c.child_fd, 'stream': c.stream.to_json()}
        input_args = {}
        for c in self.input_connections:
            input_args[c.name] = {'fd': c.child_fd, 'stream': c.stream.to_json()}
        cmd += ["--pipes", json.dumps(json.dumps(
            {'outputs': output_args, 'inputs': input_args}))]
        # add a socket if the module has a web interface
        if self.module.is_app:
            cmd += ["--socket", self.interface_name]
        # API access
        cmd += ["--api-socket", API_SOCKET]
        for (arg, value) in self.module.arguments.items():
            cmd += ["--" + arg, value]
        return cmd

    def _close_child_fds(self):
        for c in self.input_connections + self.output_connections:
            os.close(c.child_fd)

    async def _close_connections(self):
        for c in self.output_connections + self.input_connections:
            await c.disconnect()
        self.output_connections = []
        self.input_connections = []

    def _verify_monotonic_timestamps(self, data, last_ts: int, name: str):
        if len(data) == 0:
            return True
        # if there are multiple rows, check that all timestamps are increasing
        if len(data) > 1 and np.min(np.diff(data['timestamp'])) <= 0:
            min_idx = np.argmin(np.diff(data['timestamp']))
            msg = ("Non-monotonic timestamp in new data to stream [%s] (%d<=%d)" %
                   (name, data['timestamp'][min_idx + 1], data['timestamp'][min_idx]))
            log.warning(msg)
            self.log(msg)
            return False
        # check to make sure the first timestamp is larger than the previous block
        if last_ts is not None:
            if last_ts >= data['timestamp'][0]:
                msg = ("Non-monotonic timestamp between writes to stream [%s] (%d<=%d)" %
                       (name, data['timestamp'][0], last_ts))
                log.warning(msg)
                self.log(msg)
                return False
        return True
