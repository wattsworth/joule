from typing import Dict, List, Optional
import logging
import asyncio
import shlex
import os
import json
import collections
import datetime

from joule.models.module import Module
from joule.models.stream import Stream
from joule.models.subscription import Subscription
from joule.models.errors import SubscriptionError
from joule.models import pipes
from joule.models.pipes.errors import EmptyPipe


# custom types
Loop = asyncio.AbstractEventLoop
StreamQueues = Dict[Stream, List[asyncio.Queue]]

popen_lock = asyncio.Lock()
log = logging.getLogger('joule')


class Worker:

    def __init__(self, my_module: Module):

        self.module: Module = my_module
        # map of subscribers (1-many) that consume module outputs
        self.subscribers: Dict[Stream, List[asyncio.Queue]] = {}
        # map of subscriptions (1-1) to feed module inputs
        self.subscriptions: Dict[Stream, Optional[Subscription]] = {}
        # map of (fd,pipe) connections to module input names
        self.input_connections: Dict[str, (int, pipes.Pipe)] = {}
        # map of (fd,pipe) connections to module output names
        self.output_connections: Dict[str, (int, pipes.Pipe)] = {}

        for (name, stream) in self.module.outputs.items():
            # add a subscriber array and an empty output connection
            self.subscribers[stream] = []
            self.output_connections[name] = None

        for (name, stream) in self.module.inputs.items():
            # add an empty subscription and an empty input connection
            self.subscriptions[stream] = None
            self.input_connections[name] = None

        self._logs = collections.deque([], maxlen=my_module.log_size)
        self.process: asyncio.subprocess.Process = None
        self.stop_requested = False

        # tunable constants
        # how long to wait for proc to stop nicely
        self.SIGTERM_TIMEOUT = 2
        # how long to wait to restart a failed process
        self.RESTART_INTERVAL = 1

    def subscribe_to_inputs(self, workers: List['Worker'], loop: Loop) -> bool:
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
                [s.unsubscribe() for s in self.subscriptions.values() if s is not None]
                return False  # cannot find all input inputs
        return True

    async def run(self, loop: Loop, restart: bool = True) -> None:
        if not self._validate_inputs():
            return
        self.stop_requested = False
        while True:
            self.log("---starting module---")
            await self._spawn_child(loop)
            self.log("---module terminated---")
            if restart and not self.stop_requested:
                log.error("Restarting failed module: %s" % self.module.name)
                await asyncio.sleep(self.RESTART_INTERVAL)
                # insert an empty block in output_queues to indicate end of
                # interval
                for queues in self.subscribers.values():
                    for queue in queues:
                        queue.put_nowait(None)
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
                "Cannot stop %s with SIGTERM, killing process" % self.module)
            self.process.kill()

    def log(self, msg):
        timestamp = datetime.datetime.now().isoformat()
        self._logs.append("[%s]: %s" % (timestamp, msg))

    @property
    def logs(self) -> List[str]:
        return list(self._logs)

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

    def _validate_inputs(self):
        for key, value in self.subscriptions.items():
            if value is None:
                log.error("Cannot start %s: no source for input [%s]" %
                          (self.module, key))
                return False
        return True

    async def _spawn_child(self, loop) -> None:
        # lock so fd's don't pollute other modules
        await popen_lock.acquire()
        pipe_task = await self._build_pipes(loop)
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
            await self._close_pipes()
            return
        self._close_child_fds()
        popen_lock.release()
        logger_task = loop.create_task(self._logger())
        await self.process.wait()
        # Unwind the tasks
        self._close_pipes()
        pipe_task.cancel()
        logger_task.cancel()
        # collect any errors
        await pipe_task
        await logger_task

    async def _logger(self):
        stream = self.process.stdout
        try:
            while True:
                bline = await stream.readline()
                if len(bline) == 0:
                    break
                line = bline.decode('UTF-8').rstrip()
                self.log(line)
        except asyncio.CancelledError:
            return

    async def _build_pipes(self, loop: Loop) -> asyncio.Task:
        tasks: List[asyncio.Task] = []
        # configure output pipes          [module]==>[worker]
        for (name, stream) in self.module.outputs.items():
            (r, w) = os.pipe()
            rf = pipes.reader_factory(r, loop)
            os.set_inheritable(w, True)
            module_output = pipes.InputPipe(name=name, stream=stream,
                                            reader_factory=rf)
            self.output_connections[name] = (w, module_output)
            tasks.append(loop.create_task(
                self._pipe_in(module_output, self.subscribers[stream])))
        # configure input pipes            [module]<==[worker]
        for (name, stream) in self.module.inputs.items():
            (r, w) = os.pipe()
            wf = pipes.writer_factory(w, loop)
            writer = await wf()
            os.set_inheritable(r, True)
            module_input = pipes.OutputPipe(name=name, stream=stream,
                                            writer=writer)
            self.input_connections[name] = (r, module_input)
            tasks.append(loop.create_task(
                self._pipe_out(self.subscriptions[stream].queue, module_input)))
        return asyncio.gather(*tasks)

    def _compose_cmd(self) -> str:
        cmd = shlex.split(self.module.exec_cmd)
        output_args = {}
        for (name, (fd, stream)) in self.output_connections.items():
            output_args[name] = {'fd': fd, 'layout': stream.layout}
        input_args = {}
        for (name, (fd, stream)) in self.input_connections.items():
            input_args[name] = {'fd': fd, 'layout': stream.layout}
        cmd += ["--pipes", json.dumps(json.dumps(
            {'outputs': output_args, 'inputs': input_args}))]
        # add a socket if the module has a web interface
        if self.module.has_interface:
            cmd += ["--socket", self._socket_path()]
        return cmd

    def _close_child_fds(self):
        for (name, (fd, pipe)) in self.output_connections.items():
            os.close(fd)
        for (name, (fd, pipe)) in self.input_connections.items():
            os.close(fd)

    def _close_pipes(self):
        for (name, (fd, pipe)) in self.output_connections.items():
            pipe.close()
        for (name, (fd, pipe)) in self.input_connections.items():
            pipe.close()

    async def _pipe_in(self, npipe, queues):
        """given a numpy pipe, get data and put it
           into each queue in [output_queues] """
        try:
            while True:
                data = await npipe.read()
                npipe.consume(len(data))
                # print("adding %d rows of data to"%len(data))
                for q in queues:
                    # print("\tworker q: %d"%id(q))
                    q.put_nowait(data)
                await asyncio.sleep(0.25)
        except EmptyPipe:
                # print("empty pipe %s, exiting loop"%npipe.name)
            return
        except asyncio.CancelledError:
            return

    async def _pipe_out(self, queue, npipe):
        try:
            while True:
                data = await queue.get()
                # TODO: handle broken intervals
                if data is not None:
                    await npipe.write(data)
                # rate limit pipe reads
                await asyncio.sleep(0.25)
        except ConnectionResetError as e:
            print("reset error, for ", npipe)
        except asyncio.CancelledError:
            return

    def _socket_path(self):
        path = "/tmp/joule-module-%d" % self.module.uuid
        try:
            os.unlink(path)
        except OSError:
            if os.path.exists(path):
                print("file exists!")
