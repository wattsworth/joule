import numpy as np
import time
import asyncio
from joule.models.pipes import Pipe
from joule.models.pipes.errors import PipeError, EmptyPipe

Loop = asyncio.AbstractEventLoop


class LocalPipe(Pipe):
    """pipe for intra-module async communication"""

    def __init__(self, layout, loop: Loop = None, name=None, buffer_size=3000, debug=False):
        super().__init__(name=name, layout=layout)
        if loop is None:
            loop = asyncio.get_event_loop()
        # tunable constants
        self.BUFFER_SIZE = buffer_size
        self.MAX_BLOCK_SIZE = int(buffer_size / 3)
        self.TIMEOUT_INTERVAL = 0.5
        self.debug = debug
        self.interval_break = False
        self.closed = False
        self.read_buffer = np.empty((0,), dtype=self.dtype)
        # initialize buffer and queue
        self.queue = asyncio.Queue(loop=loop)
        self.queued_rows = 0
        self.last_index = 0
        self.subscribers = []
        self.direction = Pipe.DIRECTION.TWOWAY

    async def read(self, flatten=False):
        self.interval_break = False
        # if the queue is empty and we have old data, just return the old data
        if self.queue.empty() and len(self.read_buffer) > 0:
            return self._format_data(self.read_buffer, flatten)

        # otherwise wait for at least one block
        while self.queue.empty():
            # if the buffer is empty and the queue is empty and the pipe is closed
            if self.queue.empty() and len(self.read_buffer) == 0 and self.closed:
                raise EmptyPipe()
            await asyncio.sleep(self.TIMEOUT_INTERVAL)

        return self._read(flatten)

    def read_nowait(self, flatten=False):
        # if the queue is empty and we have old data, just return the old data
        if self.queue.empty() and len(self.read_buffer) > 0:
            return self._format_data(self.read_buffer, flatten)

        # otherwise wait for at least one block
        while self.queue.empty():
            # if the buffer is empty and the queue is empty and the pipe is closed
            if self.queue.empty() and len(self.read_buffer) == 0 and self.closed:
                raise EmptyPipe()
            time.sleep(self.TIMEOUT_INTERVAL)

        return self._read(flatten)

    def _read(self, flatten=False):
        # now put all the queued data together in a single array with the previous data
        # this cannot be interrupted, relies on the total size of data written to the pipe
        start = 0
        end = len(self.read_buffer)
        buffer = np.empty((self.queued_rows + end,), self.dtype)
        if self.debug:
            print("[%s:read] initialized %d row buffer" % (self.name, len(buffer)))
            print("[%s:read] adding %d rows of unconsumed data" % (self.name, len(self.read_buffer)))
        buffer[start:end] = self.read_buffer
        start = end
        while not self.queue.empty():
            block = self.queue.get_nowait()
            if block is None:
                self.interval_break = True
                break
            end = start + len(block)
            buffer[start:end] = block
            start = end
            self.queued_rows -= len(block)

        self.read_buffer = buffer[:end]
        if self.debug:
            print("[%s:read] returning %d rows" % (self.name, len(self.read_buffer)))
        return self._format_data(self.read_buffer, flatten)

    @property
    def end_of_interval(self):
        return self.interval_break

    def consume(self, num_rows):
        if num_rows == 0:
            return
        if num_rows < 0:
            raise PipeError("consume called with negative offset: %d" % num_rows)
        if num_rows > len(self.read_buffer):
            raise PipeError("cannot consume %d rows: only %d available"
                            % (num_rows, len(self.read_buffer)))
        if self.debug:
            print("[%s:read] consumed %d rows" % (self.name, num_rows))
        self.read_buffer = self.read_buffer[num_rows:]

    async def write(self, data):
        # convert into a structured array
        sarray = self._apply_dtype(data)
        # send data to subscribers
        for pipe in self.subscribers:
            await pipe.write(sarray)

        self.queue.put_nowait(sarray)
        self.queued_rows += len(sarray)
        if self.debug:
            print("[%s:write] queueing block with [%d] rows" % (self.name, len(sarray)))

    async def close_interval(self):
        if self.debug:
            print("[%s:write] closing interval" % self.name)
        await self.queue.put(None)

    def close_interval_nowait(self):
        if self.debug:
            print("[%s:write] closing interval" % self.name)
        self.queue.put_nowait(None)

    async def close(self):
        self.closed = True

    def close_nowait(self):
        self.closed = True

    def write_nowait(self, data):
        # convert into a structured array
        sarray = self._apply_dtype(data)
        # send data to subscribers
        for pipe in self.subscribers:
            pipe.write_nowait(sarray)

        self.queue.put_nowait(sarray)
        self.queued_rows += len(sarray)
        if self.debug:
            print("[%s:write] queueing block with [%d] rows" % (self.name, len(sarray)))

    def subscribe(self, pipe):
        self.subscribers.append(pipe)
