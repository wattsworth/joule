from typing import List, Callable, Dict
import asyncio
import logging

from joule.models import Worker, Stream, pipes
from joule.errors import SubscriptionError
from joule.utilities.pipe_builders import request_network_input
from joule.utilities.pipe_builders import request_network_output

Tasks = List[asyncio.Task]
Loop = asyncio.AbstractEventLoop

log = logging.getLogger('joule')


class Supervisor:

    def __init__(self, workers: List[Worker]):
        self._workers = workers
        self.task: asyncio.Task = None
        self.remote_outputs: Dict[Stream, pipes.Pipe] = {}
        self.remote_inputs: Dict[Stream, pipes.Pipe] = {}

    @property
    def workers(self):
        return self._workers

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
        await self.task
        for pipe in self.remote_outputs.values():
            await pipe.close()
        for pipe in self.remote_inputs.values():
            await pipe.close()

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

    def get_socket(self, module_uuid):
        for w in self.workers:
            if w.uuid == module_uuid:
                return w.interface_socket
        return None

    async def _connect_remote_outputs(self, worker: Worker, loop: Loop):
        remote_streams = [stream for stream in worker.subscribers if stream.is_remote]
        for stream in remote_streams:
            pipe = await request_network_output(stream.remote_path, stream,
                                                stream.remote_url, loop)
            # ignore unsubscribe cb, not used
            worker.subscribe(stream, pipe)
            self.remote_outputs[stream] = pipe

    def _connect_remote_input(self, stream: Stream, pipe: pipes.Pipe, loop: Loop):
        if stream in self.remote_inputs:
            return self.remote_inputs[stream].subscribe(pipe)

        request_network_input(stream.remote_path,
                              stream, stream.remote_url, pipe, loop)
        self.remote_inputs[stream] = pipe
