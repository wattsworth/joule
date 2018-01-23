import numpy as np
import asyncio
import logging
from . import numpypipe
from joule.utils import network


MAX_ROWS = 9000  # max array size is 3000 rows


class StreamNumpyPipeWriter(numpypipe.NumpyPipe):

    def __init__(self, layout, writer=None, writer_factory=None,
                 loop=None, buffer_size=3000):
        super().__init__("REMOVE THIS ARG", layout)
        self.writer_factory = writer_factory
        self.writer = writer  
        if(loop is None):
            self.loop = asyncio.get_event_loop()
        else:
            self.loop = loop
        self.byte_buffer = b''
        # tunable constants
        self.BUFFER_SIZE = buffer_size
        self.buffer = np.zeros(self.BUFFER_SIZE, dtype=self.dtype)
        self.last_index = 0

    async def write(self, data):
        if(self.writer is None):
            self.writer = await self.writer_factory()

        # make sure dtype is structured
        sdata = self._apply_dtype(data)
        self.writer.write(sdata.tostring())
        await self.writer.drain()

    def close(self):
        if(not(self.writer is None)):
            self.writer.close()
            self.writer = None

            
async def request_writer(stream,
                         time_range=None,
                         address='127.0.0.1',
                         port='1234',
                         loop=None):

    r, w = await asyncio.open_connection(address, port, loop=loop)
    config = network.WriterConfig(stream.to_json(ini_format=True),
                                  time_range)
    msg = network.DataRequest(network.REQ_WRITE, config._asdict())
    await network.send_json(w, msg._asdict())
    resp = await network.read_json(r)
    if(resp['status'] != network.STATUS_OK):
        raise Exception(resp['message'])
    return StreamNumpyPipeWriter(stream.layout, writer=w)

