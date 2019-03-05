import asyncio
import numpy as np
import logging

from joule.models.pipes import Pipe, interval_token
from joule.models.pipes.errors import PipeError

log = logging.getLogger('joule')


class OutputPipe(Pipe):

    def __init__(self, name=None, stream=None, layout=None, close_cb=None,
                 writer: asyncio.StreamWriter=None, writer_factory=None):
        super().__init__(name=name, stream=stream, layout=layout,
                         direction=Pipe.DIRECTION.OUTPUT)
        self.writer_factory = writer_factory
        self.writer: asyncio.StreamWriter = writer
        self.close_cb = close_cb
        # caching
        self._caching = False
        self._cache_index = 0
        self._cache = None

    async def write(self, data):
        if self.closed:
            raise PipeError("Cannot write to a closed pipe")
        if not self._validate_data(data):
            return
        # make sure dtype is structured
        sdata = self._apply_dtype(data)

        if self._caching:
            for row in sdata:
                self._cache[self._cache_index] = row
                self._cache_index += 1
                if self._cache_index >= len(self._cache):
                    await self.flush_cache()
        else:
            await self._write(sdata)

    def enable_cache(self, lines: int):
        self._caching = True
        self._cache = np.empty(lines, self.dtype)
        self._cache_index = 0

    async def flush_cache(self):
        if self.closed:
            raise PipeError("Pipe is closed")
        if self._cache_index > 0:
            await self._write(self._cache[:self._cache_index])
            self._cache_index = 0
            self._cache = np.empty(len(self._cache), self.dtype)

    async def _write(self, sdata):
        if self.writer is None:
            self.writer = await self.writer_factory()

        # send data to subscribers
        for pipe in self.subscribers:
            await pipe.write(sdata)

        # send data out
        self.writer.write(sdata.tostring())
        await self.writer.drain()

    async def close_interval(self):
        if self.closed:
            raise PipeError("Pipe is closed")
        if self._caching:
            await self.flush_cache()
        self.writer.write(interval_token(self.layout).tostring())
        await self.writer.drain()

    def close_interval_nowait(self):
        if self.closed:
            raise PipeError("Pipe is closed")
        if self._cache_index > 0:
            log.warning("dumping %d rows of cached data due on %s" % (self._cache_index, self.name))
            self._cache = np.empty(len(self._cache), self.dtype)
            self._cache_index = 0
        self.writer.write(interval_token(self.layout).tostring())

    async def close(self):
        if self.closed:
            return
        # if the cache is enabled, flush it
        if self._caching:
            await self.flush_cache()
        if self.close_cb is not None:
            await self.close_cb()
        if self.writer is not None:
            self.writer.close()
            # TODO: available in python3.7
            # await self.writer.wait_closed()
            # Hack to close the transport
            await asyncio.sleep(0.01)
            self.writer = None
        # close any subscribers
        for pipe in self.subscribers:
            await pipe.close()
        self.closed = True

