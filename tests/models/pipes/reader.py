import asyncio


class QueueReader:
    def __init__(self):
        self._queue = asyncio.Queue()

    async def put(self, data):
        await self._queue.put(data)

    async def read(self, bytes: int):
        return await self._queue.get()

    def at_eof(self):
        return self._queue.empty()