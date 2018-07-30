import asyncio


class QueueReader:
    def __init__(self, delay=0.0):
        self._queue = asyncio.Queue()
        self.delay = delay

    async def put(self, data):
        await self._queue.put(data)

    async def read(self, _: int):
        if self.delay > 0:
            await asyncio.sleep(self.delay)
        return await self._queue.get()

    def at_eof(self):
        return self._queue.empty()

