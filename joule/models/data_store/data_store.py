import numpy as np
import asyncio
from typing import List, Union, Tuple, Optional, Callable, Coroutine, TYPE_CHECKING
from abc import ABC, abstractmethod

from joule.models import pipes

if TYPE_CHECKING:
    from joule.models import Stream

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
        return {
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
    async def spawn_inserter(self, stream: 'Stream', pipe: pipes.InputPipe,
                             loop: Loop, insert_period=None) -> asyncio.Task:
        pass

    @abstractmethod
    async def extract(self, stream: 'Stream', start: Optional[int], end: Optional[int],
                      callback: Callable[[np.ndarray], Coroutine],
                      max_rows: int = None, decimation_level=None) -> (asyncio.Task, str):
        pass

    @abstractmethod
    async def remove(self, stream: 'Stream', start: Optional[int], end: Optional[int]):
        pass

    @abstractmethod
    async def destroy(self, stream):
        pass

    @abstractmethod
    async def info(self, stream: 'Stream') -> StreamInfo:
        pass

    @abstractmethod
    def close(self):
        pass
