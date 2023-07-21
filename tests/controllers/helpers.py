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
from joule.models.data_store.event_store import EventStore
from joule.models.data_store.event_store import StreamInfo as EventStreamInfo
from joule.models import (Base, DataStore, DataStream,
                          StreamInfo, DbInfo, pipes,
                          worker, EventStream)
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


class MockEventStore(EventStore):
    def __init__(self):
        self.stream_info = {}
        self.destroyed_stream_id = None

    async def initialize(self):
        pass

    async def info(self, streams: List[EventStream]) -> Dict[int, EventStreamInfo]:
        info_dict = {}
        for s in streams:
            if s in self.stream_info:
                info_dict[s.id] = self.stream_info[s]
        return info_dict

    async def destroy(self, stream: EventStream):
        self.destroyed_stream_id = stream.id


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
        self.dropped_decimations = False
        self.redecimated_data = False

    async def initialize(self, streams: List[DataStream]):
        pass

    async def insert(self, stream: DataStream,
                     data: np.ndarray, start: int, end: int):
        pass

    async def spawn_inserter(self, stream: DataStream, pipe: pipes.InputPipe, insert_period=None) -> asyncio.Task:
        async def task():
            if self.raise_data_error:
                raise DataError("test error")
            self.inserted_data = True

        return asyncio.create_task(task())

    def configure_extract(self, nchunks, nintervals=1,
                          decimation_error=False,
                          data_error=False,
                          no_data=False):
        self.nchunks = nchunks
        self.nintervals = nintervals
        self.raise_decimation_error = decimation_error
        self.raise_data_error = data_error
        self.no_data = no_data

    async def extract(self, stream: DataStream, start: Optional[int], end: Optional[int],
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

    async def intervals(self, stream: 'DataStream', start: Optional[int], end: Optional[int]):
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

    async def drop_decimations(self, stream: 'DataStream'):
        self.dropped_decimations = True

    async def decimate(self, stream: 'DataStream'):
        self.redecimated_data = True

    async def remove(self, stream: DataStream, start: Optional[int], end: Optional[int]):
        self.removed_data_bounds = (start, end)

    async def destroy(self, stream: DataStream):
        self.destroyed_stream_id = stream.id

    async def destroy_all(self):
        raise Exception("not implemented!")

    async def info(self, streams: List[DataStream]) -> Dict[int, StreamInfo]:
        info_dict = {}
        for s in streams:
            if s in self.stream_info:
                info_dict[s.id] = self.stream_info[s]
        return info_dict

    async def dbinfo(self) -> DbInfo:
        return DbInfo('/file/path', 0, 0, 0, 0)

    async def consolidate(self, stream: 'DataStream', start: Optional[int], end: Optional[int], max_gap: int) -> int:
        return 0

    def close(self):
        pass

    # -- special mock tools --
    def set_info(self, stream: DataStream, info: StreamInfo):
        self.stream_info[stream] = info


class MockWorker:
    def __init__(self, name, inputs, outputs, uuid=1, is_app=False, socket=None):
        self.name = name
        self.description = "description for %s" % name
        self.is_app = is_app
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

    def subscribe(self, stream: DataStream, pipe: pipes.LocalPipe):
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
