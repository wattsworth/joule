import numpy as np
import fcntl
import os
import contextlib

MAX_ROWS=3000 #max array size is 3000 rows

class NumpyPipe:
  """Wraps an OS pipe as a Numpy queue
     Only supports float64 streams (timestamp and data)"""
  
  def __init__(self,fd,num_streams):
    self.fd = fd
    self.cols=num_streams+1
    self.rowsize = 8*self.cols #only support float64 arrays
    self.buffer = b''

  @contextlib.contextmanager
  def open(self):
    fcntl.fcntl(self.fd,fcntl.F_SETFL, os.O_NONBLOCK)
    self.input = open(self.fd,'rb')
    yield
    self.input.close()
    
  def get(self):
    s_data = self.input.read(MAX_ROWS*self.rowsize)
    extra_bytes = (len(s_data)+len(self.buffer))%self.rowsize
    if(extra_bytes>0):
      data=np.frombuffer(self.buffer+s_data[:-extra_bytes],dtype='float64')
      self.buffer=s_data[-extra_bytes:]
    else:
      data=np.frombuffer(self.buffer+s_data,dtype='float64')
      self.buffer = []
    data.shape = len(data)//self.cols,self.cols
    return data

  def dtype(self):
      return '{cols}float64'.format(cols=self.cols)

