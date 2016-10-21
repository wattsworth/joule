import numpy as np
import fcntl
import os
import contextlib
import selectors

MAX_ROWS=3000 #max array size is 3000 rows
MAX_WAIT=2 #wait 2 seconds for data 

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
    print("got here!!!")
    self.input = open(self.fd,'rb')
    self.sel = selectors.DefaultSelector()
    self.sel.register(self.input,selectors.EVENT_READ)
    yield
    self.input.close()
    
  def get(self):
    r = self.sel.select(timeout=MAX_WAIT)
    if(len(r)==0):
      print("process hasn't returned data")
      return []
    s_data = self.input.read(MAX_ROWS*self.rowsize)
    extra_bytes = (len(s_data)+len(self.buffer))%self.rowsize
    if(extra_bytes>0):
      data=np.frombuffer(self.buffer+s_data[:-extra_bytes],dtype='float64')
      self.buffer=s_data[-extra_bytes:]
    else:
      data=np.frombuffer(self.buffer+s_data,dtype='float64')
      self.buffer = b''
    data.shape = len(data)//self.cols,self.cols
    return data

  def dtype(self):
      return '{cols}float64'.format(cols=self.cols)

