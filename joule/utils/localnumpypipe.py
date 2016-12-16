
import asyncio
import numpy as np
from . import errors, numpypipe


class LocalNumpyPipe(numpypipe.NumpyPipe):
    """pipe for intra-module async communication"""

    def __init__(self, name, layout, buffer_size=3000):
        super().__init__(name, layout)
        # tunable constants
        self.BUFFER_SIZE = buffer_size
        self.MAX_BLOCK_SIZE = int(buffer_size / 3)

        # initialize buffer and queue
        self.queue = asyncio.Queue()
        self.buffer = np.zeros(self.BUFFER_SIZE, dtype=self.dtype)
        self.last_index = 0
        self.subscribers = []

    async def read(self, flatten=False):
        if(not self.queue.empty() or self.last_index == 0):
            # pull new data from queue or the buffer is empty so
            # we have to wait for new data
            while(not self._buffer_full()):
                block = await self.queue.get()
                self.buffer[
                    self.last_index:self.last_index + len(block)] = block
                self.last_index += len(block)
                if(self._buffer_full):
                    break  # no more room in buffer
                if(self.queue.empty()):
                    break  # no more data in buffer

        return self._format_data(self.buffer[:self.last_index], flatten)

    def read_nowait(self, flatten=False):
        while(not self._buffer_full() and not self.queue.empty()):
            block = self.queue.get_nowait()
            self.buffer[self.last_index:self.last_index + len(block)] = block
            self.last_index += len(block)
            if(self._buffer_full()):
                break  # no more room in buffer
        return self._format_data(self.buffer[:self.last_index], flatten)

    def consume(self, num_rows):
        if(num_rows > self.last_index):
            raise errors.NumpyPipeError("cannot consume %d rows: only %d available"
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
