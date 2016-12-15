import numpy as np


class NumpyPipe:

  def __init__(self,name,layout):

    self.name = name
    self.layout = layout
    self.dtype = self._layout_to_dtype(layout)

  def read(self,flatten=False):
    raise NumpyPipeError("abstract method must be implemented by child")

  def write(self,data):
    raise NumpyPipeError("abstract method must be implemented by child")

  def consume(self,num_rows):
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


  def _apply_dtype(self,data):
    """convert [data] to the pipe's [dtype]"""
    if data.ndim == 1:
      # already a structured array just verify its data type
      if data.dtype != self.dtype:
        raise NumpyPipeError("wrong dtype for 1D (structured) array")
      return data
    elif data.ndim == 2:
        # Convert to structured array
        sarray = np.zeros(data.shape[0], dtype=self.dtype)
        try:
          sarray['timestamp'] = data[:,0]
          # Need the squeeze in case sarray['data'] is 1 dimensional
          sarray['data'] = np.squeeze(data[:,1:])
          return sarray
        except (IndexError, ValueError):
          raise ValueError("wrong number of fields for this data type")
    else:
      raise NumpyPipeError("wrong number of dimensions in array")

  def _chunks(self, data):
    """Yield successive MAX_BLOCK_SIZE chunks of data."""
    for i in range(0, len(data), self.MAX_BLOCK_SIZE):
      yield data[i:i + self.MAX_BLOCK_SIZE]

  def _format_data(self,data,flatten):
    if(flatten==False):      
      return data
    else:
      return  np.c_[data['timestamp'][:,None],data['data']]
      
class NumpyPipeError(Exception):
  """base class for numpypipe exceptions"""

