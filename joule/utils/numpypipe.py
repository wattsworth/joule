import numpy as np


class NumpyPipe:

  def __init__(self,name,layout):
    self.name = name
    self.dtype = self._layout_to_dtype(layout)
    
  def read(self):
    raise NumpyPipeError("abstract method must be implemented by child")

  def write(self):
    raise NumpyPipeError("abstract method must be implemented by child")

  def consume(self):
    raise NumpyPipeError("abstract method must be implemented by child")


  def _layout_to_dtype(self,layout):
    ltype = layout.split('_')[0]
    lcount = int(layout.split('_')[1])
    if ltype.startswith('int'):
        atype = '<i' + str(int(ltype[3:]) // 8)
    elif ltype.startswith('uint'):
        atype = '<u' + str(int(ltype[4:]) // 8)
    elif ltype.startswith('float'):
        atype = '<f' + str(int(ltype[5:]) // 8)
    else:
        raise NumpyPipeError("bad layout")
    return np.dtype([('timestamp', '<i8'), ('data', atype, lcount)])


  def _apply_dtype(data):
    """convert [data] to the pipe's [dtype]"""
    pass
  
class NumpyPipeError(Exception):
  """base class for numpypipe exceptions"""

