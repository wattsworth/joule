from typing import Dict, List, Callable
import logging
import asyncio
import shlex
import os
import json
import collections
import datetime
import psutil

from joule.models.module import Module
from joule.models.stream import Stream
from joule.models.folder import get_stream_path
from joule.models.errors import SubscriptionError
from joule.models import pipes
from joule.models.pipes.errors import EmptyPipe

# custom types
Loop = asyncio.AbstractEventLoop
Subscribers = Dict[Stream, List[pipes.Pipe]]

popen_lock = asyncio.Lock()
log = logging.getLogger('joule')

SOCKET_BASE = "wattsworth.joule.%d"


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
    def __init__(self, pid, create_time, cpu_percent, memory):
        self.pid = pid
        self.create_time = create_time
        self.cpu_percent = cpu_percent
        self.memory = memory

    def to_json(self):
        return {
            'pid': self.pid,
            'create_time': self.create_time,
            'cpu_percent': self.cpu_percent,
            'memory': self.memory
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
        self.RESTART_INTERVAL = 1

    def statistics(self) -> Statistics:
        # gather process statistics
        if self.process is not None:
            try:
                p = psutil.Process(pid=self.process.pid)
            except psutil.NoSuchProcess:
                return Statistics(None, None, None, None)

            with p.oneshot():
                return Statistics(p.pid,
                                  p.create_time(),
                                  p.cpu_percent(),
                                  p.memory_info().rss)
        else:
            # worker is not running, no statistics available
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
    def has_interface(self):
        return self.module.has_interface

    @property
    def interface_socket(self):
        if self.module.has_interface:
            return b'\x00' + (SOCKET_BASE % self.module.uuid).encode('ascii')
        return None

    @property
    def interface_name(self):
        if self.module.has_interface:
            return SOCKET_BASE % self.module.uuid
        return "none"

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
                return
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
                        await pipe.close_interval()
            else:
                break

    async def stop(self, loop: Loop) -> None:
        self.stop_requested = True
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
            self.process.kill()

    def log(self, msg):
        timestamp = datetime.datetime.now().isoformat()
        self._logs.append("[%s]: %s" % (timestamp, msg))
        if self.process is None:
            pid = '???'
        else:
            pid = self.process.pid
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
            i = self.subscribers[stream].index(pipe)
            del self.subscribers[stream][i]

        return unsubscribe

    async def _spawn_child(self, subscribe: Callable[[Stream, pipes.Pipe], Callable],
                           loop: Loop) -> None:
        # lock so fd's don't pollute other modules
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
        create = asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT, close_fds=False)
        try:
            self.process = await create
        except Exception as e:
            self.process = None
            self.log("ERROR: cannot start module: \n\t%s" % e)
            self.module.status = Module.STATUS.FAILED
            log.error("Cannot start [%s]" % self.module.name)
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
                self._output_handler(pipe, self.subscribers[stream])))

        return asyncio.gather(*tasks)

    @staticmethod
    async def _output_handler(child_output: pipes.Pipe,
                              subscribers: List[pipes.Pipe]):
        """given a numpy pipe, get data and put it
           into each queue in [output_queues] """
        try:
            while True:
                data = await child_output.read()
                child_output.consume(len(data))
                if len(data) > 0:
                    for s in subscribers:
                        try:
                            await s.write(data)
                        except (ConnectionResetError, BrokenPipeError):
                            pass  # TODO: remove the subscriber
                if child_output.end_of_interval:
                    for s in subscribers:
                        await s.close_interval()
                await asyncio.sleep(0.25)
        except (EmptyPipe, asyncio.CancelledError):
            pass

    async def _subscribe_to_inputs(self,
                                   subscribe: Callable[[Stream, pipes.Pipe], Callable],
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
                unsubscribe = subscribe(stream, pipe)
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
        if self.module.has_interface:
            cmd += ["--socket", self.interface_name]
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
