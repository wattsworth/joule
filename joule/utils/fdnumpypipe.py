import numpy as np
import asyncio
from . import numpypipe
import os
import sys

MAX_ROWS = 3000  # max array size is 3000 rows


class FdNumpyPipe(numpypipe.NumpyPipe):

    def __init__(self, name, fd, layout, loop=None):
        super().__init__(name, layout)
        self.fd = fd
        if(loop is None):
            self.loop = asyncio.get_event_loop()
        else:
            self.loop = loop
        self.buffer = b''
        self.reader = None  # initialized by _open_read()
        self.writer = None  # initialized by _open_write()
        self.transport = None

    async def read(self, flatten=False):
        await self._open_read()
        rowbytes = self.dtype.itemsize
        raw = await self.reader.read(MAX_ROWS * rowbytes)

        if(len(raw) == 0):
            # print("empty read in pipe %s, closing"%self.name)
            # self.close()
            raise EmptyPipe

        extra_bytes = (len(raw) + len(self.buffer)) % rowbytes
        # TODO: optimize for common case where buffer is empty
        if(extra_bytes > 0):
            data = np.fromstring(
                self.buffer + raw[:-extra_bytes], dtype=self.dtype)
            self.buffer = raw[-extra_bytes:]
        else:
            data = np.fromstring(self.buffer + raw, dtype=self.dtype)
            self.buffer = b''
        return self._format_data(data, flatten)

    def consume(self, num_rows):
        pass

    async def write(self, data):
        await self._open_write()
        # make sure dtype is structured
        sdata = self._apply_dtype(data)
        self.writer.write(sdata.tostring())

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
