import enum
from typing import TYPE_CHECKING, List
import numpy as np
import logging

from joule.models.pipes.errors import PipeError

if TYPE_CHECKING:  # pragma: no cover
    from joule.models import (Module, Stream)

log = logging.getLogger('joule')


class Pipe:
    """
    This encapsulates streams and connects to modules.
    Some more infos2

    .. note::

       There are many different kinds of pipes

    """

    class DIRECTION(enum.Enum):
        INPUT = enum.auto()
        OUTPUT = enum.auto()
        TWOWAY = enum.auto()

    def __init__(self, name=None, direction=None, module=None, stream=None, layout=None):
        """

        :param name: optional name for the pipe, useful for debugging
        :param direction: data flow
        :type direction: DIRECTION
        :param module: what??
        :param stream: optional stream
        :param layout: the data layout
        """
        self.name: str = name
        self.direction: Pipe.DIRECTION = direction
        self.module: 'Module' = module
        self.stream: 'Stream' = stream
        self._layout = layout
        self.closed = False
        self.decimation_level = 1
        self.subscribers: List['Pipe'] = []

    def __repr__(self):
        return '<joule.models.Pipe name=%r direction=%r layout=%r>' % (
            self.name, self.direction.name, self.layout)

    def enable_cache(self, lines: int):
        """
        Turn on caching for pipe writes. Data is only transmitted once the cache is full.
        This improves system performance especially if :meth:`write` is called
        rapidly with short arrays. Once enabled, caching cannot be disabled.

        Args:
            lines: cache size

        """
        if self.direction == Pipe.DIRECTION.INPUT:
            raise PipeError("cannot control cache on input pipes")
        raise PipeError("abstract method must be implemented by child")

    async def flush_cache(self):
        """
        Force a pipe flush even if the cache is not full. Raises an error if caching is not
        enabled.

        """
        if self.direction == Pipe.DIRECTION.INPUT:
            raise PipeError("cannot control cache on input pipes")
        raise PipeError("abstract method must be implemented by child")

    async def read(self, flatten=False) -> np.ndarray:
        """
        Read stream data. By default this method returns a structured
        array with ``timestamp`` and ``data`` fields. This method is a coroutine.

        Args:
            flatten: return an unstructured array (flat 2D matrix) with timestamps in the first column

        Returns:
            numpy.ndarray

        >>> data = await pipe.read()
        [1, 2, 3]
        >>> data = await pipe.read(flatten=True)
        # the same data is returned again
        [1,2,3]
        >>> pipe.consume(len(data))
        # next call to read will return only new data
        """
        if self.direction == Pipe.DIRECTION.OUTPUT:
            raise PipeError("cannot read from an output pipe")

        raise PipeError("abstract method must be implemented by child")

    def consume(self, num_rows):
        """
        Flush data from the read buffer. The next call to :meth:`read` will
        return any unflushed data followed by new incoming data.

        Args:
            num_rows: number of rows to flush from the read buffer

        """

        if self.direction == Pipe.DIRECTION.OUTPUT:
            raise PipeError("cannot consume from an output pipe")
        raise PipeError("abstract method must be implemented by child")

    @property
    def end_of_interval(self):
        return False

    async def write(self, data):
        """
        Write timestamped data to the pipe. Timestamps must be monotonically increasing
        and should not overlap with existing stream data in the database. This method is a coroutine.

        Args:
            data (numpy.ndarray): May be a structured array with ``timestamp`` and ``data`` fields
            or an unstructured array with timestamps in the first column.

        >>> await pipe.write([[1000, 2, 3],[1001, 3, 4]])

        """
        if self.direction == Pipe.DIRECTION.INPUT:
            raise PipeError("cannot write to an input pipe")
        raise PipeError("abstract method must be implemented by child")

    async def close_interval(self):
        """
        Signal a break in the data stream. This should be used to indicate missing data.
        Data returned from :meth:`read` will be chunked by interval boundaries.

        """
        if self.direction == Pipe.DIRECTION.INPUT:
            raise PipeError("cannot write to an input pipe")
        raise PipeError("abstract method must be implemented by child")

    def close_interval_nowait(self):
        """
        Signal a break in the data stream. This will dumped cached data and should generally
        not be used. Instead use the coroutine :meth:`close_interval`.

        """
        pass  # pragma: no cover

    def subscribe(self, pipe):
        if self.direction == Pipe.DIRECTION.INPUT:
            raise PipeError("cannot subscribe to an input pipe")

        self.subscribers.append(pipe)

        def unsubscribe():
            i = self.subscribers.index(pipe)
            del self.subscribers[i]

        return unsubscribe

    async def close(self):
        """
        Close the pipe. This also closes any subscribers. If ``close_cb`` is defined
        it will be executed before the subscribers are closed.

        """
        # close the pipe, optionally implemented by the child
        pass  # pragma: no cover

    def change_layout(self, layout: str):
        raise PipeError("layout cannot be changed")

    @property
    def layout(self) -> str:
        if self._layout is not None:
            return self._layout
        elif self.stream is not None:
            return self.stream.layout
        else:
            raise ValueError("pipe has no layout")

    @property
    def dtype(self) -> np.dtype:
        return compute_dtype(self.layout)

    @property
    def decimated(self) -> bool:
        if self.decimation_level > 1:
            return True
        else:
            return False

    def _apply_dtype(self, data: np.ndarray) -> np.ndarray:
        """convert [data] to the pipe's [dtype]"""
        if data.ndim == 1:
            # already a structured array just verify its data type
            if data.dtype != self.dtype:
                raise PipeError("wrong dtype for 1D (structured) array" +
                                "[%s] != req type [%s]" % (data.dtype,
                                                           self.dtype))
            return data
        elif data.ndim == 2:
            # Convert to structured array
            sarray = np.zeros(data.shape[0], dtype=self.dtype)
            try:
                sarray['timestamp'] = data[:, 0]
                # Need the squeeze in case sarray['data'] is 1 dimensional
                sarray['data'] = np.squeeze(data[:, 1:])
                return sarray
            except (IndexError, ValueError):
                raise PipeError("wrong number of fields for this data type")
        else:
            raise PipeError("wrong number of dimensions in array")

    @staticmethod
    def _format_data(data, flatten):
        if flatten:
            return np.c_[data['timestamp'][:, None], data['data']]
        else:
            return data

    @staticmethod
    def _validate_data(data):
        if type(data) is not np.ndarray:
            raise PipeError("invalid data type must be a structured array or 2D matrix")
        # check for valid data type
        try:
            if (len(data) == 0) or len(data[0]) == 0:
                log.info("pipe write called with no data")
                return False
        except TypeError:
            raise PipeError("invalid data type must be a structured array or 2D matrix")
        return True


def interval_token(layout):
    nelem = int(layout.split('_')[1])
    token = np.zeros(1, dtype=compute_dtype(layout))
    token['timestamp'] = 0
    token['data'] = np.zeros(nelem)
    return token


def find_interval_token(raw: bytes, layout):
    token = interval_token(layout)[0]
    token_bytes = token.tostring()
    index = raw.find(token_bytes)
    if index == -1:
        return None
    # this data *may* have an interval, need to check if the token
    # is aligned to a row
    data = np.frombuffer(raw, dtype=compute_dtype(layout))
    i = 0
    for row in data:
        if np.array_equal(row, token):
            return i * len(token_bytes), (i + 1) * len(token_bytes)
        i += 1

    # suprious match, not aligned to a row
    return None


def compute_dtype(layout: str) -> np.dtype:
    try:
        ltype = layout.split('_')[0]
        lcount = int(layout.split('_')[1])
        if ltype.startswith('int'):
            atype = '<i' + str(int(ltype[3:]) // 8)
        elif ltype.startswith('uint'):
            atype = '<u' + str(int(ltype[4:]) // 8)
        elif ltype.startswith('float'):
            atype = '<f' + str(int(ltype[5:]) // 8)
        else:
            raise ValueError()
        return np.dtype([('timestamp', '<i8'), ('data', atype, lcount)])
    except (IndexError, ValueError):
        raise ValueError("bad layout: [%s]" % layout)
