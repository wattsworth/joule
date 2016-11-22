import numpy as np
import asyncio
import os

MAX_ROWS=3000 #max array size is 3000 rows

class NumpyPipe:

  def __init__(self,fd,stream,loop):
    """ given a file descriptor [fd] and a [stream], provide numpy array
    access to data in [fd] as an asynchronous iterator"""
    self.fd = fd
    self.loop = loop
    self.stream = stream
    self.num_cols = stream.data_width
    self.buffer = b''
    self.reader = None #initialized by _open_read()
    self.writer = None #initialized by _open_write()
    self.transport = None
    
  async def read(self):
    await self._open_read()
    
    if self.reader.at_eof():
      self.close()
      raise PipeClosed
    
    rowsize = self.num_cols*8
    s_data = await self.reader.read(MAX_ROWS*rowsize)

    if(len(s_data)==0):
      self.close()
      raise PipeClosed
    
    extra_bytes = (len(s_data)+len(self.buffer))%rowsize
    if(extra_bytes>0):
      data=np.frombuffer(self.buffer+s_data[:-extra_bytes],dtype='float64')
      self.buffer=s_data[-extra_bytes:]
    else:
      data=np.frombuffer(self.buffer+s_data,dtype='float64')
      self.buffer = b''
    data.shape = len(data)//self.num_cols,self.num_cols
    return data


  async def write(self,data):
    await self._open_write()
    self.writer.write(data.tobytes())

  async def _open_read(self):
    """initialize reader if not already setup"""
    if(self.reader is not None):
      return
    
    self.reader = asyncio.StreamReader()
    reader_protocol = asyncio.StreamReaderProtocol(self.reader)
    f = open(self.fd,'rb')
    (self.transport,_) = await self.loop.\
                         connect_read_pipe(lambda: reader_protocol, f)
    
  async def _open_write(self):
    if(self.writer is not None):
      return
    
    write_protocol = asyncio.StreamReaderProtocol(asyncio.StreamReader())
    f = open(self.fd,'wb')
    (self.transport, _) = await self.loop.connect_write_pipe(
      lambda: write_protocol, f)
    self.writer = asyncio.StreamWriter(self.transport, write_protocol, None, self.loop)

  def close(self):
    if(self.transport is not None):
      self.transport.close()
      self.transport = None
    try:
      os.close(self.fd)
    except OSError:
      pass

class NumpyPipeError(Exception):
  """Base class for exceptions in this module"""
  pass

class PipeClosed(NumpyPipeError):
  pass

  
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
