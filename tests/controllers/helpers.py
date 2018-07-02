from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from typing import List
import numpy as np
import asyncio
from typing import Optional, Callable, Coroutine

from joule.models import (Base, DataStore, Stream, StreamInfo, pipes)
from joule.services import parse_pipe_config
from tests import helpers

Loop = asyncio.AbstractEventLoop


def create_db(pipe_configs: List[str]) -> Session:
    # create a database
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    db = Session(bind=engine)

    for pipe_config in pipe_configs:
        parse_pipe_config.run(pipe_config, db)

    db.commit()
    return db


class MockStore(DataStore):
    def __init__(self):
        self.stream_info = {}
        self.nchunks = 3

    async def initialize(self, streams: List[Stream]):
        pass

    async def insert(self, stream: Stream,
                     data: np.ndarray, start: int, end: int):
        pass

    async def spawn_inserter(self, stream: Stream, pipe: pipes.InputPipe,
                             loop: Loop, insert_period=None) -> asyncio.Task:
        pass

    def configure_extract(self, nchunks):
        self.nchunks = nchunks

    async def extract(self, stream: Stream, start: Optional[int], end: Optional[int],
                      callback: Callable[[np.ndarray, str, bool], Coroutine],
                      max_rows: int = None, decimation_level=None):
        for x in range(self.nchunks):
            await callback(helpers.create_data(stream.layout), stream.layout, False)

    async def remove(self, stream: Stream, start: Optional[int], end: Optional[int]):
        pass

    async def destroy(self, stream: Stream):
        pass

    async def info(self, stream: Stream) -> StreamInfo:
        return self.stream_info[stream]

    def close(self):
        pass

    # -- special mock tools --
    def set_info(self, stream: Stream, info: StreamInfo):
        self.stream_info[stream] = info
