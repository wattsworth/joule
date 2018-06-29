import numpy as np
import sys
from joule.models.pipes import Pipe, find_interval_token
from joule.models.pipes.errors import PipeError, EmptyPipe


class InputPipe(Pipe):

    def __init__(self, name=None, stream=None, layout=None,
                 reader=None, reader_factory=None,
                 close_cb=None, buffer_size=3000):
        super().__init__(name=name, stream=stream, direction=Pipe.DIRECTION.INPUT, layout=layout)
        self.reader_factory = reader_factory
        self.reader = reader
        self.close_cb = close_cb
        self.byte_buffer = b''
        self.unprocessed_raw = []
        self.interval_break = False
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

        # Note: this assumes the interval token is always unbroken
        # only get new data if we've processed everything we have
        if len(self.unprocessed_raw) > 0:
            raw = self.unprocessed_raw
            self.unprocessed_raw = []
        else:
            if self.reader.at_eof():
                raise EmptyPipe()
            raw = await self.reader.read(max_rows * rowbytes)

        # check for an interval
        self.interval_break = False
        loc = find_interval_token(raw, self.layout)
        if loc is not None:
            self.unprocessed_raw = raw[loc[1]:]
            raw = raw[:loc[0]]
            self.interval_break = True

        extra_bytes = (len(raw) + len(self.byte_buffer)) % rowbytes

        if extra_bytes > 0:
            data = np.frombuffer(
                self.byte_buffer + raw[:-extra_bytes], dtype=self.dtype)
            self.byte_buffer = raw[-extra_bytes:]
        elif len(self.byte_buffer) > 0:
            data = np.frombuffer(self.byte_buffer + raw, dtype=self.dtype)
            self.byte_buffer = b''
        else:  # common case where byte_buffer is empty
            data = np.frombuffer(raw, dtype=self.dtype)
            self.byte_buffer = b''

        # append data onto buffer
        self.buffer[self.last_index:self.last_index + len(data)] = data
        self.last_index += len(data)
        return self._format_data(self.buffer[:self.last_index], flatten)

    def consume(self, num_rows):
        if num_rows == 0:
            return  # nothing to do
        if num_rows < 0:
            print("WARNING: NumpyPipe::consume called with negative offset: %d" % num_rows)
            return

        if num_rows > self.last_index:
            raise PipeError("cannot consume %d rows: only %d available"
                            % (num_rows, self.last_index))
        self.buffer = np.roll(self.buffer, -1 * num_rows)
        self.last_index -= num_rows

    @property
    def end_of_interval(self):
        return self.interval_break

    def close(self):
        if self.close_cb is not None:
            self.close_cb()
