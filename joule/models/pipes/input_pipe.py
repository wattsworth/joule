import numpy as np
import logging
import asyncio
from joule.models.pipes import Pipe, find_interval_token
from joule.models.pipes.errors import PipeError, EmptyPipe

log = logging.getLogger('joule')


class InputPipe(Pipe):

    def __init__(self, name=None, stream=None, layout=None,
                 reader=None, reader_factory=None,
                 close_cb=None, buffer_size=10000):
        super().__init__(name=name, stream=stream, direction=Pipe.DIRECTION.INPUT, layout=layout)
        self.reader_factory = reader_factory
        self.reader = reader
        self.close_cb = close_cb
        self.byte_buffer = b''
        self.unprocessed_np_buffer = b''
        self.interval_break = False
        # tunable constant
        self.BUFFER_SIZE = buffer_size
        self.buffer = np.zeros(self.BUFFER_SIZE*2, dtype=self.dtype)
        self.last_index = 0

    async def read(self, flatten=False):
        if self.reader is None:
            self.reader = await self.reader_factory()

        rowbytes = self.dtype.itemsize
        max_rows = self.BUFFER_SIZE - self.last_index
        # see if we can fit any more data into the buffer
        if max_rows == 0:
            return self._format_data(self.buffer[:self.last_index], flatten)

        nbytes = 0  # make sure we get more than 0 bytes from the read
        while nbytes == 0:
            if self.reader.at_eof():
                if self.last_index == 0:
                    raise EmptyPipe()
                return self._format_data(self.buffer[:self.last_index], flatten)

            raw = await self.reader.read(max_rows * rowbytes)
            nbytes = len(raw)
            if nbytes == 0:
                await asyncio.sleep(0.1)

        # extra_bytes: number of leftover bytes after % rowbytes
        # byte_buffer: the extra_bytes from the last read
        # unprocessed_np_buffer: data leftover from an interval break in the previous read
        extra_bytes = (len(raw) + len(self.byte_buffer)) % rowbytes

        if extra_bytes > 0:
            np_buffer = self.byte_buffer + raw[:-extra_bytes]
            self.byte_buffer = raw[-extra_bytes:]
        elif len(self.byte_buffer) > 0:
            np_buffer = self.byte_buffer + raw
            self.byte_buffer = b''
        else:  # common case where byte_buffer is empty and no extra bytes
            np_buffer = raw
            self.byte_buffer = b''

        # append unprocessed np_buffer from previous read
        if len(self.unprocessed_np_buffer) > 0:
            np_buffer = self.unprocessed_np_buffer + np_buffer
            self.unprocessed_np_buffer = b''

        # check for an interval
        self.interval_break = False
        loc = find_interval_token(np_buffer, self.layout)
        if loc is not None:
            self.unprocessed_np_buffer = np_buffer[loc[1]:]
            np_buffer = np_buffer[:loc[0]]
            self.interval_break = True

        data = np.frombuffer(np_buffer, dtype=self.dtype)

        # append data onto buffer
        self.buffer[self.last_index:self.last_index + len(data)] = data
        self.last_index += len(data)
        return self._format_data(self.buffer[:self.last_index], flatten)

    def consume(self, num_rows):
        if num_rows == 0:
            return  # nothing to do
        if num_rows < 0:
            log.warning("InputPipe::consume called with negative offset: %d" % num_rows)
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
