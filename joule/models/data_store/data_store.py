import numpy as np
import asyncio
from typing import List, Union, Tuple, Optional, Callable, Coroutine, TYPE_CHECKING, Dict
from abc import ABC, abstractmethod

from joule.models import pipes

if TYPE_CHECKING:
    from joule.models import DataStream

Loop = asyncio.AbstractEventLoop
# starting and ending timestamps
Interval = Tuple[int, int]

Data = Union[Interval, np.array]


class StreamInfo:
    def __init__(self, start: Optional[int], end: Optional[int], rows: int,
                 total_time: int = 0, bytes: int = 0):
        self.start = start
        self.end = end
        self.rows = rows
        self.bytes = bytes
        self.total_time = total_time

    def __repr__(self):
        return "<DataStreamInfo start=%r end=%r rows=%r, total_time=%r>" % (
            self.start, self.end, self.rows, self.total_time)

    def to_json(self):
        return {
            "start": self.start,
            "end": self.end,
            "rows": self.rows,
            "bytes": self.bytes,
            "total_time": self.total_time
        }
    

class DbInfo:
    def __init__(self, path: str, other: int, reserved: int, free: int, size: int):
        self.path = path
        self.other = other
        self.reserved = reserved
        self.free = free
        self.size = size

    def to_json(self):
        return {
            "path": self.path,
            "other": self.other,
            "reserved": self.reserved,
            "free": self.free,
            "size": self.size
        }


class DataStore(ABC):  # pragma: no cover

    @abstractmethod
    async def initialize(self, streams: List['DataStream']):
        pass

    @abstractmethod
    async def insert(self, stream: 'DataStream',
                     data: np.ndarray, start: int, end: int):
        pass

    @abstractmethod
    async def consolidate(self, stream: 'DataStream', start: Optional[int], end: Optional[int],
                          max_gap: int) -> int:
        pass

    @abstractmethod
    async def drop_decimations(self, stream: 'DataStream'):
        pass

    @abstractmethod
    async def decimate(self, stream: 'DataStream'):
        pass

    @abstractmethod
    async def spawn_inserter(self, stream: 'DataStream', pipe: pipes.Pipe, insert_period=None) -> asyncio.Task:
        pass

    @abstractmethod
    async def intervals(self, stream: 'DataStream', start: Optional[int], end: Optional[int]):
        pass

    @abstractmethod
    async def extract(self, stream: 'DataStream', start: Optional[int], end: Optional[int],
                      callback: Callable[[np.ndarray, str, bool], Coroutine],
                      max_rows: int = None, decimation_level=None):
        pass

    @abstractmethod
    async def remove(self, stream: 'DataStream', start: Optional[int], end: Optional[int]):
        pass

    @abstractmethod
    async def destroy(self, stream: 'DataStream'):
        pass

    @abstractmethod
    async def destroy_all(self):
        pass

    @abstractmethod
    async def info(self, streams: List['DataStream']) -> Dict[int, StreamInfo]:
        pass

    @abstractmethod
    async def dbinfo(self) -> DbInfo:
        pass

    @abstractmethod
    async def close(self):
        pass
