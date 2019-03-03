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
        self._reader_close = None
        self.byte_buffer = b''
        self.unprocessed_np_buffer = b''
        self.interval_break = False
        # tunable constant
        self.BUFFER_SIZE = buffer_size
        """Note: The StreamReader.read coroutine hangs even if the write
        side of the pipe is closed so the call is wrapped in a wait_for"""
        self.TIMEOUT_INTERVAL = 0.5
        self.buffer = np.zeros(self.BUFFER_SIZE * 2, dtype=self.dtype)
        self.last_index = 0

    async def read(self, flatten=False):
        if self.reader is None:
            self.reader, self._reader_close = await self.reader_factory()
        if self.closed:
            # this happens if close is called before the first read
            if self._reader_close is not None:
                self._reader_close()
            raise PipeError("Cannot read from a closed pipe")
        rowbytes = self.dtype.itemsize
        max_rows = self.BUFFER_SIZE - (
                   self.last_index + len(self.unprocessed_np_buffer) % rowbytes)

        if max_rows == 0:
            # buffer is full, this must be consumed before a new read
            return self._format_data(self.buffer[:self.last_index], flatten)

        nbytes = 0  # make sure we get more than 0 bytes from the read
        raw = b''
        while nbytes == 0:
            if self.reader.at_eof():
                if (len(self.unprocessed_np_buffer) == 0 and
                        self.last_index == 0):
                    raise EmptyPipe()
                break
            try:
                raw = await asyncio.wait_for(self.reader.read(max_rows * rowbytes),
                                             self.TIMEOUT_INTERVAL)
            except asyncio.TimeoutError:
                pass

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
            self.unprocessed_np_buffer = self.unprocessed_np_buffer + np_buffer
            # check if we can process all the data, if not
            # store the extra in unprocessed_np_buffer
            max_bytes = max_rows * rowbytes
            if len(self.unprocessed_np_buffer) <= max_bytes:
                np_buffer = self.unprocessed_np_buffer
                self.unprocessed_np_buffer = b''
            else:
                np_buffer = self.unprocessed_np_buffer[:max_bytes]
                self.unprocessed_np_buffer = self.unprocessed_np_buffer[max_bytes:]

        # check for an interval
        self.interval_break = False
        loc = find_interval_token(np_buffer, self.layout)
        if loc is not None:
            self.unprocessed_np_buffer = np_buffer[loc[1]:] + self.unprocessed_np_buffer
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
            raise PipeError("consume called with negative offset: %d" % num_rows)
        if num_rows > self.last_index:
            raise PipeError("cannot consume %d rows: only %d available"
                            % (num_rows, self.last_index))
        self.buffer = np.roll(self.buffer, -1 * num_rows)
        self.last_index -= num_rows

    @property
    def end_of_interval(self):
        return self.interval_break

    async def close(self):
        if self._reader_close is not None:
            self._reader_close()
            self._reader_close = None
        self.closed = True
        if self.close_cb is not None:
            # used to close socket pipes
            await self.close_cb()
