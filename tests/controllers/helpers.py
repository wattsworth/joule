from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from typing import List
import numpy as np
import asyncio
import pdb

from joule.models import (Base, DataStore, Stream, Subscription, StreamInfo)
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
                     data: np.array, start: int, end: int):
        pass

    async def spawn_inserter(self, stream: Stream, subscription: Subscription,
                             loop: Loop) -> asyncio.Task:
        pass

    def configure_extract(self, nchunks):
        self.nchunks = nchunks

    async def extract(self, stream: Stream, start: int, end: int,
                      output: asyncio.Queue,
                      max_rows: int = None, decimation_level=None):
        for x in range(self.nchunks):
            await output.put(helpers.create_data(stream.layout))

    async def remove(self, stream: Stream, start: int, end: int):
        pass

    async def info(self, stream: Stream) -> StreamInfo:
        return self.stream_info[stream]

    def close(self):
        pass

    # -- special mock tools --
    def set_info(self, stream: Stream, info: StreamInfo):
        self.stream_info[stream] = info
