import numpy as np
import asyncio
import logging
from . import numpypipe
from .. import network


MAX_ROWS = 9000  # max array size is 3000 rows


class StreamNumpyPipeReader(numpypipe.NumpyPipe):

    def __init__(self, layout, reader=None,
                 reader_factory=None, loop=None, buffer_size=3000):
        super().__init__("REMOVE_THIS_ARG", layout)
        self.reader_factory = reader_factory
        self.reader = reader
        if(loop is None):
            self.loop = asyncio.get_event_loop()
        else:
            self.loop = loop
        self.byte_buffer = b''
        # tunable constants
        self.BUFFER_SIZE = buffer_size
        self.buffer = np.zeros(self.BUFFER_SIZE, dtype=self.dtype)
        self.last_index = 0

    async def read(self, flatten=False):
        if(self.reader is None):
            self.reader = await self.reader_factory()
            
        rowbytes = self.dtype.itemsize
        max_rows = self.BUFFER_SIZE - self.last_index
        if(max_rows == 0):
            return self._format_data(self.buffer[:self.last_index], flatten)

        raw = await self.reader.read(max_rows * rowbytes)

        if(len(raw) == 0):
            # print("empty read in pipe %s, closing"%self.name)
            # self.close()
            raise numpypipe.EmptyPipe

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

    def close(self):
        pass


async def request_reader(path,
                         decimation=1,
                         time_range=None,
                         address='127.0.0.1',
                         port='1234',
                         loop=None):

    r, w = await asyncio.open_connection(address, port, loop=loop)
    config = network.ReaderConfig(path, decimation, time_range)
    msg = network.DataRequest(network.REQ_READ, config._asdict())
    await network.send_json(w, msg._asdict())
    resp = await network.read_json(r)
    if(resp['status'] != network.STATUS_OK):
        msg = "Request to read [%s] failed: %s" %\
                      (path, resp['message'])
        logging.error(msg)
        raise Exception(msg)
    layout = resp['message']
    return StreamNumpyPipeReader(layout, reader=r)

