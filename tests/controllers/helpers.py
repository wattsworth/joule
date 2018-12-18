from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from typing import List, Dict, Tuple
import numpy as np
import asyncio
import argparse
import psycopg2
import testing.postgresql

from unittest import mock
from typing import Optional, Callable, Coroutine

from joule.models.data_store.errors import DataError, InsufficientDecimationError
from joule.models import (Base, DataStore, Stream,
                          StreamInfo, DbInfo, pipes,
                          worker)
from joule.errors import SubscriptionError
from joule.services import parse_pipe_config
from tests import helpers

Loop = asyncio.AbstractEventLoop


def create_db(pipe_configs: List[str]) -> Tuple[Session, testing.postgresql.Postgresql]:
    postgresql = testing.postgresql.Postgresql()
    db_url = postgresql.url()
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute("CREATE SCHEMA metadata")
    conn.commit()
    conn.close()
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    db = Session(bind=engine)
    for pipe_config in pipe_configs:
        parse_pipe_config.run(pipe_config, db)

    db.commit()
    return db, postgresql


class MockStore(DataStore):
    def __init__(self):
        self.stream_info = {}
        # stubs to track data controller execution
        self.nchunks = 3
        self.nintervals = 1
        self.raise_data_error = False
        self.raise_decimation_error = False
        self.no_data = False
        self.raise_data_error = False
        self.inserted_data = False
        self.removed_data_bounds = (None, None)
        self.destroyed_stream_id = None
        self.raise_data_error = False

    async def initialize(self, streams: List[Stream]):
        pass

    async def insert(self, stream: Stream,
                     data: np.ndarray, start: int, end: int):
        pass

    def spawn_inserter(self, stream: Stream, pipe: pipes.InputPipe,
                       loop: Loop, insert_period=None) -> asyncio.Task:
        async def task():
            if self.raise_data_error:
                raise DataError("test error")
            self.inserted_data = True

        return loop.create_task(task())

    def configure_extract(self, nchunks, nintervals=1,
                          decimation_error=False,
                          data_error=False,
                          no_data=False):
        self.nchunks = nchunks
        self.nintervals = nintervals
        self.raise_decimation_error = decimation_error
        self.raise_data_error = data_error
        self.no_data = no_data

    async def extract(self, stream: Stream, start: Optional[int], end: Optional[int],
                      callback: Callable[[np.ndarray, str, bool], Coroutine],
                      max_rows: int = None, decimation_level=1):
        if self.no_data:
            return  # do not call the callback func
        if self.raise_data_error:
            raise DataError("nilmdb error")
        if self.raise_decimation_error:
            raise InsufficientDecimationError("insufficient decimation")
        if decimation_level is not None and decimation_level > 1:
            layout = stream.decimated_layout
        else:
            decimation_level = 1
            layout = stream.layout
        for i in range(self.nintervals):
            for x in range(self.nchunks):
                await callback(helpers.create_data(layout, length=25), layout, decimation_level)
            if i < (self.nintervals - 1):
                await callback(pipes.interval_token(layout), layout, decimation_level)

    async def intervals(self, stream: 'Stream', start: Optional[int], end: Optional[int]):
        if start is None:
            if end is None:
                # just a random set of intervals
                return [[0, 100], [200, 300]]
            else:
                return [[end - 10, end]]
        else:
            if end is None:
                return [[start, start + 10]]
            else:
                return [[start, end]]

    async def remove(self, stream: Stream, start: Optional[int], end: Optional[int]):
        self.removed_data_bounds = (start, end)

    async def destroy(self, stream: Stream):
        self.destroyed_stream_id = stream.id

    async def info(self, streams: List[Stream]) -> Dict[int, StreamInfo]:
        info_dict = {}
        for s in streams:
            if s in self.stream_info:
                info_dict[s.id] = self.stream_info[s]
        return info_dict

    async def dbinfo(self) -> DbInfo:
        return DbInfo('/file/path', 0, 0, 0, 0)

    def close(self):
        pass

    # -- special mock tools --
    def set_info(self, stream: Stream, info: StreamInfo):
        self.stream_info[stream] = info


class MockWorker:
    def __init__(self, name, inputs, outputs, uuid=1, has_interface=False, socket=None):
        self.name = name
        self.description = "description for %s" % name
        self.has_interface = has_interface
        self.uuid = uuid
        self.interface_socket = socket
        self.input_connections = []
        for (name, path) in inputs.items():
            self.input_connections.append(argparse.Namespace(name=name, location=path))
        self.output_connections = []
        for (name, path) in outputs.items():
            self.output_connections.append(argparse.Namespace(name=name, location=path))

    async def statistics(self) -> worker.Statistics:
        return worker.Statistics(100, 100, 1.0, 100)

    @property
    def logs(self):
        return ["log entry1", "log entry2"]


class MockSupervisor:
    def __init__(self):
        self.subscription_pipe = None
        self.subscribed_stream = None
        self.raise_error = False
        # if True do not close the pipe (simulate an ongoing transaction)
        self.hang_pipe = False
        self.unsubscribe_mock = mock.Mock()
        self.unsubscribe_calls = 0

    def unsubscribe(self):
        self.unsubscribe_calls += 1

    def subscribe(self, stream: Stream, pipe: pipes.LocalPipe, loop: Loop):
        if self.raise_error:
            raise SubscriptionError()

        self.subscribed_stream = stream
        while True:
            try:
                data = self.subscription_pipe.read_nowait()
                self.subscription_pipe.consume(len(data))
                pipe.write_nowait(data)
            except pipes.EmptyPipe:
                if not self.hang_pipe:
                    pipe.close_nowait()
                break
            if self.subscription_pipe.end_of_interval:
                pipe.close_interval_nowait()
        # return a mock as the unsubscribe callback
        return self.unsubscribe
