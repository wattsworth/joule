import datetime

import numpy as np
import os
import pdb
import configparser
import asyncio
import unittest
import testing.postgresql
import psycopg2
from sqlalchemy import create_engine, pool
from sqlalchemy.orm import Session
from collections import deque
from typing import Optional
from icecream import ic
from joule.models import DataStream, Element, Base, Pipe
from joule.models.pipes import LocalPipe
from joule.models.pipes.errors import PipeError
from joule.errors import EmptyPipeError


def create_data(layout: str,
                length=100,
                step=1000,  # in us
                start=1476152086000000):  # 10 Oct 2016 10:15PM
    """Create a random block of NilmDB data with [layout] structure"""
    ts = np.arange(start, start + step * length, step, dtype=np.uint64)

    # Convert to structured array
    (ltype, lcount, dtype) = parse_layout(layout)
    sarray = np.zeros(len(ts), dtype=dtype)
    if "float" in ltype:
        data = np.random.rand(length, lcount)
    elif "uint" in ltype:
        data = np.random.randint(0, high=100, size=(
            length, lcount), dtype=dtype[1].base)
    else:
        data = np.random.randint(-50, high=50,
                                 size=(length, lcount), dtype=dtype[1].base)

    sarray['timestamp'] = ts
    # Need the squeeze in case sarray['data'] is 1 dimensional
    sarray['data'] = data
    return sarray


def create_stream(name, layout, id=0) -> DataStream:
    (ltype, lcount, dtype) = parse_layout(layout)
    datatype = DataStream.DATATYPE[ltype.upper()]

    return DataStream(name=name, datatype=datatype, id=id,
                      elements=[Element(name="e%d" % j, index=j,
                                        display_type=Element.DISPLAYTYPE.CONTINUOUS) for j in range(lcount)],
                      updated_at=datetime.datetime.utcnow())


def to_chunks(data, chunk_size):
    """Yield successive MAX_BLOCK_SIZE chunks of data."""
    for i in range(0, len(data), chunk_size):
        yield data[i:i + chunk_size]


def parse_layout(layout):
    ltype = layout.split('_')[0]
    lcount = int(layout.split('_')[1])
    if ltype.startswith('int'):
        atype = '<i' + str(int(ltype[3:]) // 8)
    elif ltype.startswith('uint'):
        atype = '<u' + str(int(ltype[4:]) // 8)
    elif ltype.startswith('float'):
        atype = '<f' + str(int(ltype[5:]) // 8)
    else:
        raise ValueError("bad layout")
    dtype = np.dtype([('timestamp', '<i8'), ('data', atype, (lcount,))])
    return ltype, lcount, dtype


def parse_configs(config_str):
    config = configparser.ConfigParser()
    config.read_string(config_str)
    return config


def mock_stream_info(streams):
    """pass in array of stream_info's:
       [['/test/path','float32_3'],
       ['/test/path2','float32_5'],...]
       returns a function to mock stream_info as a side_effect"""

    def stream_info(path):
        for stream in streams:
            if stream[0] == path:
                return [stream]
        return []

    return stream_info


class AsyncTestCase(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        self.loop.set_debug(True)
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        closed = self.loop.is_closed()
        if not closed:
            self.loop.call_soon(self.loop.stop)
            self.loop.run_forever()
            self.loop.close()
        asyncio.set_event_loop(None)

        # close any remaining pipes, uvloop tends to leave
        # pipes after the loop is closed
        for str_fd in set(os.listdir('/proc/self/fd/')):
            fd = int(str_fd)
            try:
                fstat = os.fstat(fd)
                # if stat.S_ISFIFO(fstat.st_mode):
                #    os.close(fd)
            except OSError:
                pass

        import psutil
        proc = psutil.Process()
        # print("[%d] fds" % proc.num_fds())


Postgresql = testing.postgresql.PostgresqlFactory(cache_initialized_db=True)


class DbTestCase(unittest.TestCase):

    def setUp(self):
        self.postgresql = Postgresql()  # testing.postgresql.Postgresql()
        db_url = self.postgresql.url()
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute("CREATE SCHEMA metadata")
        conn.commit()
        conn.close()
        engine = create_engine(db_url, poolclass=pool.NullPool)
        Base.metadata.create_all(engine)
        self.db = Session(bind=engine)

    def tearDown(self):
        self.db.close()
        self.postgresql.stop()


class TestingPipe(Pipe):
    # reads come out in the same blocks as the writes
    # ...wraps LocalPipe

    def __init__(self, layout: str, name: str = None, stream=None):
        super().__init__(name=name, layout=layout, stream=stream)

        self._pipe = LocalPipe(layout, name, stream)
        self._closed = False
        self.data_blocks: deque = deque()

    async def write(self, data):
        if self._closed:
            raise PipeError("Cannot write to a closed pipe")
        self.data_blocks.append(data)

    def write_nowait(self, data):
        if self._closed:
            raise PipeError("Cannot write to a closed pipe")
        self.data_blocks.append(data)

    def close_interval_no_wait(self):
        self.data_blocks.append(None)

    async def close_interval(self):
        self.data_blocks.append(None)

    def consume(self, rows):
        return self._pipe.consume(rows)

    def reread_last(self):
        self._pipe.reread_last()

    @property
    def end_of_interval(self):
        return self._pipe.end_of_interval

    async def read(self, flatten=False):
        # first write a block to the pipe if there are any waiting
        if len(self.data_blocks) > 0:
            block = self.data_blocks.popleft()
            if block is None:
                await self._pipe.close_interval()
            else:
                await self._pipe.write(block)
        elif self._closed:
            await self._pipe.close()
        # now return the result of the inner pipe's read
        return await self._pipe.read(flatten)

    def is_empty(self):
        return self._pipe.is_empty()

    async def close(self):
        self._closed = True


class TestingPipeOld(Pipe):
    # reads come out in the same blocks as the writes

    def __init__(self, layout: str, name: str = None, stream=None):
        super().__init__(name=name, layout=layout, stream=stream)
        self.data_blocks: deque = deque()
        self.last_block: Optional[np.ndarray] = None
        self._last_read = False  # flag to indicate pipe only has previously read data (see input_pipe.py)
        self.interval_break = False
        self._reread = False

    async def write(self, data):
        sarray = self._apply_dtype(data)
        self.data_blocks.append(sarray)

    def write_nowait(self, data):
        sarray = self._apply_dtype(data)
        self.data_blocks.append(sarray)

    def close_interval_no_wait(self):
        self.data_blocks.append(None)

    async def close_interval(self):
        self.data_blocks.append(None)

    def consume(self, rows):
        if self.last_block is None:
            raise Exception("Nothing to consume")
        if rows > len(self.last_block):
            raise Exception("Cannot consume %d rows, only %d available" % (
                rows, len(self.last_block)))
        if rows == len(self.last_block):
            self.last_block = None
        else:
            self.last_block = self.last_block[rows:]

    def reread_last(self):
        self._reread = True

    @property
    def end_of_interval(self):
        return self.interval_break

    async def read(self, flatten=False):
        if flatten:
            raise Exception("Not Implemented")
        if self._reread:
            self._reread = False
            if self.last_block is None or len(self.last_block) == 0:
                raise PipeError("No data left to reread")
            return self.last_block

        if len(self.data_blocks) == 0 and self.last_block is None:
            raise EmptyPipeError()
        if len(self.data_blocks) != 0:
            block = self.data_blocks.popleft()
            if len(self.data_blocks) == 0:
                self.interval_break = True
                self._last_read = True
            elif self.data_blocks[0] is None:
                self.data_blocks.popleft()
                self.interval_break = True
            else:
                self.interval_break = False

            if self.last_block is not None:
                self.last_block = np.hstack((self.last_block, block))
            else:
                self.last_block = block
        return self.last_block

    def is_empty(self):
        if self._reread:
            return False
        if self._last_read:
            return True
        if len(self.data_blocks) == 0 and self.last_block is None:
            return True
        return False
