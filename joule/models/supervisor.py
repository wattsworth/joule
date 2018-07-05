from typing import List, Callable
import asyncio
import pdb

from joule.models import Worker, Stream, pipes
from joule.models.errors import SubscriptionError

Tasks = List[asyncio.Task]
Loop = asyncio.AbstractEventLoop


class Supervisor:

    def __init__(self, workers: List[Worker]):
        self._workers = workers
        self.task: asyncio.Task = None

    @property
    def workers(self):
        return self._workers

    def start(self, loop: Loop):
        # returns a co-routine
        tasks: Tasks = []
        for worker in self._workers:
            tasks.append(loop.create_task(worker.run(self.subscribe, loop)))
        self.task = asyncio.gather(*tasks, loop=loop)

    async def stop(self, loop: Loop):
        for worker in self._workers:
            await worker.stop(loop)
        await self.task

    def subscribe(self, stream: Stream, pipe: pipes.Pipe) -> Callable:
        # find a worker producing this stream
        for worker in self._workers:
            try:
                return worker.subscribe(stream, pipe)
            except SubscriptionError:
                pass
        else:
            raise SubscriptionError("stream [%s] has no producer" % stream.name)

    def get_socket(self, module_uuid):
        for w in self.workers:
            if w.module.uuid == module_uuid:
                return w.interface_socket
        return None

    def publish(self, stream: Stream, loop: Loop):
        pass
