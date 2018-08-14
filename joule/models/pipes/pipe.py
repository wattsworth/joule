import enum
from typing import TYPE_CHECKING
import numpy as np
import logging

from joule.models.pipes.errors import PipeError

if TYPE_CHECKING:  # pragma: no cover
    from joule.models import (Module, Stream)

log = logging.getLogger('joule')


class Pipe:
    class DIRECTION(enum.Enum):
        INPUT = enum.auto()
        OUTPUT = enum.auto()
        TWOWAY = enum.auto()

    def __init__(self, name=None, direction=None, module=None, stream=None, layout=None):
        self.name: str = name
        self.direction: Pipe.DIRECTION = direction
        self.module: 'Module' = module
        self.stream: 'Stream' = stream
        self._layout = layout

    def enable_cache(self, lines: int):
        if self.direction == Pipe.DIRECTION.INPUT:
            raise PipeError("cannot control cache on input pipes")
        raise PipeError("abstract method must be implemented by child")

    async def flush_cache(self):
        if self.direction == Pipe.DIRECTION.INPUT:
            raise PipeError("cannot control cache on input pipes")
        raise PipeError("abstract method must be implemented by child")

    async def read(self, flatten=False):
        if self.direction == Pipe.DIRECTION.OUTPUT:
            raise PipeError("cannot read from an output pipe")

        raise PipeError("abstract method must be implemented by child")

    def consume(self, num_rows):
        if self.direction == Pipe.DIRECTION.OUTPUT:
            raise PipeError("cannot consume from an output pipe")
        raise PipeError("abstract method must be implemented by child")

    @property
    def end_of_interval(self):
        return False

    async def write(self, data):
        if self.direction == Pipe.DIRECTION.INPUT:
            raise PipeError("cannot write to an input pipe")
        raise PipeError("abstract method must be implemented by child")

    async def close_interval(self):
        if self.direction == Pipe.DIRECTION.INPUT:
            raise PipeError("cannot write to an input pipe")
        raise PipeError("abstract method must be implemented by child")

    async def close(self):
        # close the pipe, optionally implemented by the child
        pass  # pragma: no cover

    @property
    def layout(self):
        if self.stream is not None:
            return self.stream.layout
        return self._layout

    @property
    def dtype(self) -> np.dtype:
        return compute_dtype(self.layout)

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

    def __repr__(self):
        msg = "<Pipe(name='%s', direction=" % self.name
        if self.direction == Pipe.DIRECTION.INPUT:
            msg += 'INPUT'
        else:
            msg += 'OUTPUT'
        msg += ", module="
        if self.module is not None:
            msg += self.module.name
        else:
            msg += "[None]"
        msg += ", stream="
        if self.stream is not None:
            msg += self.stream.name
        else:
            msg += "[None]"
        msg += '>'
        return msg


def interval_token(layout):
    nelem = int(layout.split('_')[1])
    token = np.zeros(1, dtype=compute_dtype(layout))
    token['timestamp'] = 0
    token['data'] = np.zeros(nelem)
    return token


def find_interval_token(raw: bytes, layout):
    token = interval_token(layout).tostring()
    index = raw.find(token)
    if index == -1:
        return None
    return index, index + len(token)


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
