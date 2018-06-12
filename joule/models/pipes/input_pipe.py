import numpy as np

from joule.models.pipes import Pipe
from joule.models.pipes.errors import PipeError, EmptyPipe


class InputPipe(Pipe):

    def __init__(self, name=None, stream=None,
                 reader=None, reader_factory=None,
                 close_cb=None, buffer_size=3000):
        super().__init__(name=name, stream=stream, direction=Pipe.DIRECTION.INPUT)
        self.reader_factory = reader_factory
        self.reader = reader
        self.close_cb = close_cb
        self.byte_buffer = b''
        # tunable constant
        self.BUFFER_SIZE = buffer_size
        self.buffer = np.zeros(self.BUFFER_SIZE, dtype=self.dtype)
        self.last_index = 0

    async def read(self, flatten=False):
        if self.reader is None:
            self.reader = await self.reader_factory()

        rowbytes = self.dtype.itemsize
        max_rows = self.BUFFER_SIZE - self.last_index
        if max_rows == 0:
            return self._format_data(self.buffer[:self.last_index], flatten)

        raw = await self.reader.read(max_rows * rowbytes)
        # TODO: handle empty pipes, is eof the same as 0 bytes?
        if self.reader.at_eof() and (len(raw) == 0):
            raise EmptyPipe()

        extra_bytes = (len(raw) + len(self.byte_buffer)) % rowbytes
        # TODO: optimize for common case where byte_buffer is empty
        if extra_bytes > 0:
            data = np.frombuffer(
                self.byte_buffer + raw[:-extra_bytes], dtype=self.dtype)
            self.byte_buffer = raw[-extra_bytes:]
        else:
            data = np.frombuffer(self.byte_buffer + raw, dtype=self.dtype)
            self.byte_buffer = b''
        # append data onto buffer
        self.buffer[self.last_index:self.last_index + len(data)] = data
        self.last_index += len(data)
        return self._format_data(self.buffer[:self.last_index], flatten)

    def consume(self, num_rows):
        if num_rows <= 0:
            print("WARNING: NumpyPipe::consume called with negative offset: %d" % num_rows)
            return

        if num_rows > self.last_index:
            raise PipeError("cannot consume %d rows: only %d available"
                            % (num_rows, self.last_index))
        self.buffer = np.roll(self.buffer, -1 * num_rows)
        self.last_index -= num_rows

    def close(self):
        if self.close_cb is not None:
            self.close_cb()
