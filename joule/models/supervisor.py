from typing import List, Callable, Dict
import asyncio
import logging
from sqlalchemy import orm

from joule.models import Worker, Stream, Proxy, Follower, pipes
from joule.errors import SubscriptionError, ConfigurationError, ApiError

from joule.api import BaseNode

Tasks = List[asyncio.Task]
Loop = asyncio.AbstractEventLoop

log = logging.getLogger('joule')


class Supervisor:

    def __init__(self, workers: List[Worker], proxies: List[Proxy], get_node: Callable[[str], BaseNode]):
        self._workers = workers
        self._proxies = proxies
        self.get_node = get_node
        self.task: asyncio.Task = None
        self.remote_tasks: List[asyncio.Task] = []
        self.remote_inputs: Dict[Stream, pipes.Pipe] = {}

        self.REMOTE_HANDLER_RESTART_INTERVAL = 5

    @property
    def workers(self):
        return self._workers

    @property
    def proxies(self):
        return self._proxies

    async def start(self, loop: Loop):
        # returns a co-routine
        tasks: Tasks = []
        for worker in self._workers:
            await self._connect_remote_outputs(worker, loop)
            tasks.append(loop.create_task(worker.run(self.subscribe, loop)))
        self.task = asyncio.gather(*tasks, loop=loop)

    async def stop(self, loop: Loop):
        for worker in self._workers:
            await worker.stop(loop)
        try:
            await self.task
        except Exception as e:
            log.warning("Supervisor worker shutdown exception: %s " % str(e))
        for task in self.remote_tasks:
            task.cancel()
            try:
                await task
            except Exception as e:
                log.warning("Supervisor remote i/o shutdown exception: %s " % str(e))
                raise e

    async def restart_producer(self, stream: Stream, loop: Loop, msg=""):
        # find the worker who produces this stream
        for worker in self._workers:
            if worker.produces(stream):
                if msg is not None:
                    log.warning("Restarting module [%s]: %s" % (worker.name, msg))
                    worker.log("[Supervisor Restarting Module: %s]" % msg)
                await worker.restart(loop)

    def subscribe(self, stream: Stream, pipe: pipes.Pipe, loop: Loop) -> Callable:
        # if the stream is remote, connect to it
        if stream.is_remote:
            return self._connect_remote_input(stream, pipe, loop)
        # otherwise find a worker producing it
        for worker in self._workers:
            try:
                return worker.subscribe(stream, pipe)
            except SubscriptionError:
                pass
        else:
            raise SubscriptionError("stream [%s] has no producer" % stream.name)

    def get_module_socket(self, uuid):
        for w in self.workers:
            if w.uuid == uuid:
                return w.interface_socket
        return None

    def get_proxy_url(self, uuid):
        for p in self._proxies:
            if p.uuid == uuid:
                return p.url
        return None

    async def _connect_remote_outputs(self, worker: Worker, loop: Loop):
        """ Provide a pipe to the worker for each remote stream, spawn a
            task that reads from the worker's pipe and writes out to a remote
            network pipe, if the remote network pipe goes down or is not available,
            continuously try to restore it
        """
        remote_streams = [stream for stream in worker.subscribers if stream.is_remote]
        for stream in remote_streams:
            src_pipe = pipes.LocalPipe(stream.layout, loop, stream=stream)
            # ignore unsubscribe cb, not used
            worker.subscribe(stream, src_pipe)
            task = loop.create_task(self._handle_remote_output(src_pipe, stream, loop))
            self.remote_tasks.append(task)

    async def _handle_remote_output(self, src_pipe: pipes.Pipe, dest_stream: Stream, loop: Loop):
        """
        Continuously tries to make a connection to dest_stream and write src_pipe's data to it
        """
        dest_pipe = None
        node = self.get_node(dest_stream.remote_node)
        if node is None:
            log.error("output requested from [%s] but this node is not a follower" % dest_stream.remote_node)
            return
        try:
            while True:
                try:
                    dest_pipe = await node.data_write(dest_stream.remote_path)
                    while True:
                        data = await src_pipe.read()
                        await dest_pipe.write(data)
                        src_pipe.consume(len(data))

                except ConfigurationError as e:
                    log.error("Subscriber::_handle_remote_output: %s" % str(e))
                    await asyncio.sleep(self.REMOTE_HANDLER_RESTART_INTERVAL)
        except asyncio.CancelledError:
            pass
        finally:
            await src_pipe.close()
            if dest_pipe is not None:
                await dest_pipe.close()
            await node.close()

    def _connect_remote_input(self, stream: Stream, pipe: pipes.Pipe, loop: Loop):
        """
        Spawn a task that maintains a connection with [stream] and provides the data to [pipe]
        """
        # somebody is already listening to stream, just subscribe to that pipe
        if stream in self.remote_inputs:
            return self.remote_inputs[stream].subscribe(pipe)

        # this is the first subscriber, spawn an input task to feed the pipe
        task = loop.create_task(self._handle_remote_input(stream, pipe, loop))

        self.remote_inputs[stream] = pipe
        self.remote_tasks.append(task)

    async def _handle_remote_input(self, src_stream: Stream, dest_pipe: pipes.Pipe, loop: Loop):
        """
        Continuously tries to make a connection to src_stream and write its data to dest_pipe
        """
        src_pipe = None
        node = self.get_node(src_stream.remote_node)
        if node is None:
            log.error("input requested from [%s] but this node is not a follower" % src_stream.remote_node)
            return

        try:
            while True:
                try:
                    src_pipe = await node.data_subscribe(src_stream.remote_path)
                    try:
                        while True:
                            data = await src_pipe.read()
                            if not dest_pipe.closed:
                                await dest_pipe.write(data)
                            else:
                                log.info(
                                    "destination [%s] is closed, OK if this is during shutdown" % dest_pipe.stream.name)
                            src_pipe.consume(len(data))
                    except pipes.EmptyPipe:
                        await dest_pipe.close_interval()
                    log.error("Subscriber:: _handle_remote_input: connection terminated unexepectedly")
                except (ConfigurationError, ApiError) as e:
                    log.error("Subscriber::_handle_remote_input: %s" % str(e))
                await asyncio.sleep(self.REMOTE_HANDLER_RESTART_INTERVAL)
        except asyncio.CancelledError:
            pass
        finally:
            if src_pipe is not None:
                await src_pipe.close()
            await dest_pipe.close()
            await node.close()
