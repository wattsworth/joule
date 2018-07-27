from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from typing import List
import numpy as np
import asyncio
import argparse
from typing import Optional, Callable, Coroutine

from joule.models import (Base, DataStore, Stream, StreamInfo, DbInfo, pipes, worker)
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
        # stubs to track data controller execution
        self.nchunks = 3
        self.inserted_data = False
        self.removed_data_bounds = (None, None)
        self.destroyed_stream_id = None

    async def initialize(self, streams: List[Stream]):
        pass

    async def insert(self, stream: Stream,
                     data: np.ndarray, start: int, end: int):
        pass

    async def spawn_inserter(self, stream: Stream, pipe: pipes.InputPipe,
                             loop: Loop, insert_period=None) -> asyncio.Task:
        async def task():
            self.inserted_data = True
        return loop.create_task(task())

    def configure_extract(self, nchunks):
        self.nchunks = nchunks

    async def extract(self, stream: Stream, start: Optional[int], end: Optional[int],
                      callback: Callable[[np.ndarray, str, bool], Coroutine],
                      max_rows: int = None, decimation_level=None):
        for x in range(self.nchunks):
            await callback(helpers.create_data(stream.layout), stream.layout, False)

    async def remove(self, stream: Stream, start: Optional[int], end: Optional[int]):
        self.removed_data_bounds = (start, end)

    async def destroy(self, stream: Stream):
        self.destroyed_stream_id = stream.id

    async def info(self, stream: Stream) -> StreamInfo:
        return self.stream_info[stream]

    async def dbinfo(self) -> DbInfo:
        return DbInfo('/file/path', 0, 0, 0, 0)

    def close(self):
        pass

    # -- special mock tools --
    def set_info(self, stream: Stream, info: StreamInfo):
        self.stream_info[stream] = info


class MockWorker:
    def __init__(self, name, inputs, outputs, uuid=1, has_interface=False):
        self.name = name
        self.description = "description for %s" % name
        self.has_interface = has_interface
        self.uuid = uuid
        self.input_connections= []
        for (name, path) in inputs.items():
            self.input_connections.append(argparse.Namespace(name=name, location=path))
        self.output_connections = []
        for (name, path) in outputs.items():
            self.output_connections.append(argparse.Namespace(name=name, location=path))

    def statistics(self) -> worker.Statistics:
        return worker.Statistics(100, 100, 1.0, 100)

    @property
    def logs(self):
        return ["log entry1", "log entry2"]



