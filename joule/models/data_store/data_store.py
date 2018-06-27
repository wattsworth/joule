import numpy as np
import asyncio
from typing import List, Union, Tuple, TYPE_CHECKING
from abc import ABC, abstractmethod

if TYPE_CHECKING:
    from joule.models import Stream, Subscription

Loop = asyncio.AbstractEventLoop
# starting and ending timestamps
Interval = Tuple[int, int]

Data = Union[Interval, np.array]


class StreamInfo:
    def __init__(self, start: int, end: int, rows: int):
        self.start = start
        self.end = end
        self.rows = rows

    def to_json(self):
        return{
            "start": self.start,
            "end": self.end,
            "rows": self.rows
        }


class DataStore(ABC):

    @abstractmethod
    async def initialize(self, streams: List['Stream']):
        pass

    @abstractmethod
    async def insert(self, stream: 'Stream',
                     data: np.array, start: int, end: int):
        pass

    @abstractmethod
    async def spawn_inserter(self, stream: 'Stream', subscription: 'Subscription',
                             loop: Loop) -> asyncio.Task:
        pass

    @abstractmethod
    async def extract(self, stream: 'Stream', start: int, end: int,
                output: asyncio.Queue,
                max_rows: int = None, decimation_level=None):
        pass

    @abstractmethod
    async def remove(self, stream: 'Stream', start: int, end: int):
        pass

    @abstractmethod
    async def info(self, stream: 'Stream') -> StreamInfo:
        pass

    @abstractmethod
    def close(self):
        pass