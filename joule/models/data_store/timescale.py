import asyncio
from typing import List, Optional, Callable, Coroutine, Dict
import numpy as np
import asyncpg

from joule.models import Stream, pipes
from joule.models.data_store.data_store import DataStore, StreamInfo, DbInfo

Loop = asyncio.AbstractEventLoop


class TimescaleStore(DataStore):

    def __init__(self, host: str, port: int, user: str, database: str,
                 password: str, insert_period: float,
                 cleanup_period: float, loop: Loop):
        self.host = host
        self.dsn = "postgres://%s:%s@%s:%d/%s" % (user, password, host, port, database)
        self.decimation_factor = 4
        self.insert_period = insert_period
        self.cleanup_period = cleanup_period
        self.loop = loop
        self.conn = None

    async def initialize(self, stream: List[Stream]) -> None:
        self.conn = await asyncpg.connect(self.dsn)
        await self.conn.execute('''
        CREATE TABLE name(''')
    async def insert(self, stream: 'Stream',
                     data: np.ndarray, start: int, end: int):
        pass

    async def spawn_inserter(self, stream: 'Stream', pipe: pipes.Pipe,
                             loop: Loop, insert_period=None) -> asyncio.Task:
        pass

    async def intervals(self, stream: 'Stream', start: Optional[int], end: Optional[int]):
        pass

    async def extract(self, stream: 'Stream', start: Optional[int], end: Optional[int],
                      callback: Callable[[np.ndarray, str, bool], Coroutine],
                      max_rows: int = None, decimation_level=None):
        pass

    async def remove(self, stream: 'Stream', start: Optional[int], end: Optional[int]):
        pass

    async def destroy(self, stream: 'Stream'):
        pass

    async def info(self, streams: List['Stream']) -> Dict[int, StreamInfo]:
        pass

    async def dbinfo(self) -> DbInfo:
        pass

    def close(self):
        pass
