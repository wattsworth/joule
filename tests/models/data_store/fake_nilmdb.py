from typing import Dict
from aiohttp import web
from aiohttp.test_utils import unused_port
import numpy as np
import multiprocessing
from joule.constants import EndPoints
from tests import helpers


class FakeStream:
    def __init__(self, layout, start=None, end=None, rows=0, intervals=None):
        self.layout = layout
        self.start = start
        self.end = end
        self.rows = rows
        self.intervals = intervals
        self.metadata = {}
        if start is not None and end is not None:
            if self.intervals is None:
                self.intervals = [[start, end]]

    @property
    def dtype(self):
        ltype = self.layout.split('_')[0]
        lcount = int(self.layout.split('_')[1])
        atype = '??'
        if ltype.startswith('int'):
            atype = '<i' + str(int(ltype[3:]) // 8)
        elif ltype.startswith('uint'):
            atype = '<u' + str(int(ltype[4:]) // 8)
        elif ltype.startswith('float'):
            atype = '<f' + str(int(ltype[5:]) // 8)
        return np.dtype([('timestamp', '<i8'), ('data', atype, lcount)])
