
import asyncio
import numpy as np
from . import errors, numpypipe

class LocalNumpyPipe(numpypipe.NumpyPipe):
  """pipe for intra-module async communication"""

  def __init__(self,name,layout):
    super().__init__(name,layout)
    #tunable constants
    self.BUFFER_SIZE=3000
    self.MAX_BLOCK_SIZE=1000
    #initialize buffer and queue
    self.queue = asyncio.Queue()
    self.buffer = np.zeros(self.BUFFER_SIZE,dtype=self.dtype)
    self.last_index = 0
    self.subscribers = []
    
  async def read(self):
    if(self.queue.empty()):
      #see if we can just return whats in the buffer
      if(self.last_index>0):
        return self.buffer[:self.last_index]
      #...nothing in the buffer so we have to wait for new data
    while(True):
      block = await self.queue.get()
      self.buffer[self.last_index:self.last_index+len(block)]=block
      self.last_index += len(block)
      if(self.last_index+self.MAX_BLOCK_SIZE<self.BUFFER_SIZE):
        break #no more room in buffer
      if(self.queue.empty()):
        break #no more data in buffer
    return self.buffer[:self.last_index]

  def consume(self,num_rows):
    if(num_rows>self.last_index):
      raise errors.NumpyPipeError("cannot consume %d rows: only %d available"\
                                  %(num_rows,self.last_index))
    self.buffer = np.roll(self.buffer,-1*num_rows)
    self.last_index-=num_rows
  
  async def write(self,data):
    #break into blocks...
    self.queue.put_nowait(data)
    for pipe in self.subscribers:
      await pipe.write(data)

  def subscribe(self,pipe):
    self.subscribers.append(pipe)
