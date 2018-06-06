import enum
from typing import TYPE_CHECKING
import numpy as np

from joule.models.pipes.errors import PipeError

if TYPE_CHECKING:
    from joule.models import (Module, Stream)


class Pipe:

    class DIRECTION(enum.Enum):
        INPUT = enum.auto()
        OUTPUT = enum.auto()
        TWOWAY = enum.auto()

    def __init__(self, name=None, direction=None, module=None, stream=None):
        self.name: str = name
        self.direction: Pipe.DIRECTION = direction
        self.module: 'Module' = module
        self.stream: 'Stream' = stream

    def read(self, flatten=False):
        if self.direction == Pipe.DIRECTION.OUTPUT:
            raise PipeError("cannot read from an output pipe")

        raise PipeError("abstract method must be implemented by child")

    def write(self, data):
        if self.direction == Pipe.DIRECTION.INPUT:
            raise PipeError("cannot write to an input pipe")
        raise PipeError("abstract method must be implemented by child")

    def consume(self, num_rows):
        if self.direction == Pipe.DIRECTION.OUTPUT:
            raise PipeError("cannot consume from an output pipe")
        raise PipeError("abstract method must be implemented by child")

    def close(self):
        pass  # close the pipe, optionally implemented by the child

    @property
    def layout(self):
        return self.stream.layout

    @property
    def dtype(self):
        ltype = self.layout.split('_')[0]
        lcount = int(self.layout.split('_')[1])
        if ltype.startswith('int'):
            atype = '<i' + str(int(ltype[3:]) // 8)
        elif ltype.startswith('uint'):
            atype = '<u' + str(int(ltype[4:]) // 8)
        elif ltype.startswith('float'):
            atype = '<f' + str(int(ltype[5:]) // 8)
        else:
            raise PipeError("bad layout")
        return np.dtype([('timestamp', '<i8'), ('data', atype, lcount)])

    def _apply_dtype(self, data):
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
                raise ValueError("wrong number of fields for this data type")
        else:
            raise PipeError("wrong number of dimensions in array")

    @staticmethod
    def _format_data(data, flatten):
        if flatten:
            return np.c_[data['timestamp'][:, None], data['data']]
        else:
            return data

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
