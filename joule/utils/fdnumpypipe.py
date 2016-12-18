import numpy as np
import asyncio
from . import numpypipe
import os
import sys

MAX_ROWS = 9000  # max array size is 3000 rows


class FdNumpyPipe(numpypipe.NumpyPipe):

    def __init__(self, name, fd, layout, loop=None, buffer_size=3000):
        super().__init__(name, layout)
        self.fd = fd
        if(loop is None):
            self.loop = asyncio.get_event_loop()
        else:
            self.loop = loop
        self.byte_buffer = b''
        # tunable constants
        self.BUFFER_SIZE = buffer_size
        self.buffer = np.zeros(self.BUFFER_SIZE, dtype=self.dtype)
        self.last_index = 0
        self.reader = None  # initialized by _open_read()
        self.writer = None  # initialized by _open_write()
        self.transport = None

    async def read(self, flatten=False):
        await self._open_read()
        rowbytes = self.dtype.itemsize
        max_rows = self.BUFFER_SIZE - self.last_index
        if(max_rows == 0):
            return self._format_data(self.buffer[:self.last_index], flatten)

        raw = await self.reader.read(max_rows * rowbytes)

        if(len(raw) == 0):
            # print("empty read in pipe %s, closing"%self.name)
            # self.close()
            raise EmptyPipe

        extra_bytes = (len(raw) + len(self.byte_buffer)) % rowbytes
        # TODO: optimize for common case where byte_buffer is empty
        if(extra_bytes > 0):
            data = np.fromstring(
                self.byte_buffer + raw[:-extra_bytes], dtype=self.dtype)
            self.byte_buffer = raw[-extra_bytes:]
        else:
            data = np.fromstring(self.byte_buffer + raw, dtype=self.dtype)
            self.byte_buffer = b''
        # append data onto buffer
        self.buffer[
            self.last_index:self.last_index + len(data)] = data
        self.last_index += len(data)
        return self._format_data(self.buffer[:self.last_index], flatten)

    def consume(self, num_rows):
        if(num_rows > self.last_index):
            raise numpypipe.NumpyPipeError("cannot consume %d rows: only %d available"
                                           % (num_rows, self.last_index))
        self.buffer = np.roll(self.buffer, -1 * num_rows)
        self.last_index -= num_rows

    async def write(self, data):
        await self._open_write()
        # make sure dtype is structured
        sdata = self._apply_dtype(data)
        # print("writing %d rows (%d bytes) to fd[%d]"%\
        #    (len(sdata),len(sdata.tostring()),self.fd))
        sys.stdout.flush()
        self.writer.write(sdata.tostring())
        await self.writer.drain()

    async def _open_read(self):
        """initialize reader if not already setup"""
        if(self.reader is not None):
            return

        self.reader = asyncio.StreamReader()
        reader_protocol = asyncio.StreamReaderProtocol(self.reader)
        f = open(self.fd, 'rb')
        (self.transport, _) = await self.loop.\
            connect_read_pipe(lambda: reader_protocol, f)

    async def _open_write(self):
        if(self.writer is not None):
            return

        write_protocol = asyncio.StreamReaderProtocol(asyncio.StreamReader())
        f = open(self.fd, 'wb')
        (self.transport, _) = await self.loop.connect_write_pipe(
            lambda: write_protocol, f)
        sys.stdout.flush()
        self.writer = asyncio.StreamWriter(
            self.transport, write_protocol, None, self.loop)

    def close(self):
        if(self.transport is not None):
            self.transport.close()
            self.transport = None
        try:
            os.close(self.fd)
            pass
        except OSError:
            pass


class NumpyPipeError(Exception):
    """Base class for exceptions in this module"""
    pass


class EmptyPipe(NumpyPipeError):
    pass


"""
Will work in 3.6 (hopefully!)

async def numpypipe(stream,num_cols):
  rowsize = num_cols*8
  buffer = b''
  while(not buffer.at_eof()):
    s_data = await stream.read(MAX_ROWS*rowsize)
    extra_bytes = (len(s_data)+len(buffer))%rowsize
    if(extra_bytes>0):
      data=np.frombuffer(buffer+s_data[:-extra_bytes],dtype='float64')
      buffer=s_data[-extra_bytes:]
    else:
      data=np.frombuffer(buffer+s_data,dtype='float64')
      buffer = b''
    data.shape = len(data)//num_cols,num_cols
    yield data

"""
