import numpy as np
import asyncio
from joule.models.pipes import Pipe
from joule.models.pipes.errors import PipeError

Loop = asyncio.AbstractEventLoop


class LocalPipe(Pipe):
    """pipe for intra-module async communication"""

    def __init__(self, layout, loop:Loop, buffer_size=3000, debug=False):
        super().__init__(layout=layout)
        # tunable constants
        self.BUFFER_SIZE = buffer_size
        self.MAX_BLOCK_SIZE = int(buffer_size / 3)
        self.debug = debug
        self.interval_break = False
        # initialize buffer and queue
        self.queue = asyncio.Queue(loop=loop)
        self.buffer = np.zeros(self.BUFFER_SIZE, dtype=self.dtype)
        self.last_index = 0
        self.subscribers = []
        self.direction = Pipe.DIRECTION.TWOWAY

    async def read(self, flatten=False):
        self.interval_break = False
        if not self.queue.empty() or self.last_index == 0:
            # pull new data from queue or the buffer is empty so
            # we have to wait for new data
            while not self._buffer_full():
                block = await self.queue.get()
                if block is None:
                    self.interval_break = True
                    break
                self.buffer[
                    self.last_index:self.last_index + len(block)] = block
                if self.debug:
                    if self._buffer_full():
                        msg = "buffer FULL"
                    else:
                        msg = "not full"
                    print("adding [%d block] to index %d, %s" %
                          (len(block), self.last_index, msg))
                self.last_index += len(block)
                if self._buffer_full():
                    break  # no more room in buffer
                if self.queue.empty():
                    break  # no more data in buffer

        return self._format_data(self.buffer[:self.last_index], flatten)

    def read_nowait(self, flatten=False):
        self.interval_break = False
        while not self._buffer_full() and not self.queue.empty():
            block = self.queue.get_nowait()
            if block is None:
                self.interval_break = True
                break  # end of interval
            self.buffer[self.last_index:self.last_index + len(block)] = block
            self.last_index += len(block)
            if self._buffer_full():
                break  # no more room in buffer
        return self._format_data(self.buffer[:self.last_index], flatten)

    @property
    def end_of_interval(self):
        return self.interval_break

    def consume(self, num_rows):
        if num_rows <= 0:
            print("WARNING: NumpyPipe::consume called with negative offset: %d" % num_rows)
            return
        if num_rows > self.last_index:
            raise PipeError("cannot consume %d rows: only %d available"
                                 % (num_rows, self.last_index))
        self.buffer = np.roll(self.buffer, -1 * num_rows)
        self.last_index -= num_rows

    async def write(self, data):
        # convert into a structured array
        sarray = self._apply_dtype(data)
        # send data to subscribers
        for pipe in self.subscribers:
            await pipe.write(sarray)

        # add blocks of data to our queue
        for block in self._chunks(sarray):
            self.queue.put_nowait(block)

    async def close_interval(self):
        await self.queue.put(None)

    def write_nowait(self, data):
        # convert into a structured array
        sarray = self._apply_dtype(data)
        # send data to subscribers
        for pipe in self.subscribers:
            pipe.write_nowait(sarray)

        # add blocks of data to our queue
        for block in self._chunks(sarray):
            self.queue.put_nowait(block)

    def subscribe(self, pipe):
        self.subscribers.append(pipe)

    def _buffer_full(self):
        return self.last_index + self.MAX_BLOCK_SIZE > self.BUFFER_SIZE

    def _chunks(self, data):
        """Yield successive MAX_BLOCK_SIZE chunks of data."""
        for i in range(0, len(data), self.MAX_BLOCK_SIZE):
            yield data[i:i + self.MAX_BLOCK_SIZE]

