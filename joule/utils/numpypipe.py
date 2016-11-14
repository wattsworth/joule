import numpy as np

MAX_ROWS=3000 #max array size is 3000 rows

class NumpyPipe:

  def __init__(self,stream,num_cols):
    self.stream = stream
    self.num_cols = num_cols
    self.buffer = b''
    
  def __aiter__(self):
    return self

  async def __anext__(self):
    rowsize = self.num_cols*8
    while(not self.stream.at_eof()):
      s_data = await self.stream.read(MAX_ROWS*rowsize)
      if(len(s_data)==0):
        raise StopAsyncIteration
      extra_bytes = (len(s_data)+len(self.buffer))%rowsize
      if(extra_bytes>0):
        data=np.frombuffer(self.buffer+s_data[:-extra_bytes],dtype='float64')
        self.buffer=s_data[-extra_bytes:]
      else:
        data=np.frombuffer(self.buffer+s_data,dtype='float64')
        self.buffer = b''
      data.shape = len(data)//self.num_cols,self.num_cols
      return data
    raise StopAsyncIteration
  
"""
Will work in 3.6 (hopefully!)

async def numpypipe(stream,num_cols):
  rowsize = num_cols*8
  buffer = b''
  while(not buffer.at_eof()):
    s_data = await stream.read(MAX_ROWS*rowsize)
    extra_bytes = (len(s_data)+len(buffer))%rowsize
    if(extra_bytes>0):
      data=np.frombuffer(buffer+s_data[:-extra_bytes],dtype='float64')
      buffer=s_data[-extra_bytes:]
    else:
      data=np.frombuffer(buffer+s_data,dtype='float64')
      buffer = b''
    data.shape = len(data)//num_cols,num_cols
    yield data

"""
