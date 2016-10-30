from joule.procdb import client as procdb_client
import logging
import asyncio
import shlex
from . import inputmodule
from joule.utils import numpypipe


class Worker:

  def __init__(self,module,procdb_client):
    super().__init__()
    self.observers = []
    self.process = None
    self.pipe = None
    self.module = module
    self.procdb_client = procdb_client
    
  def subscribe(self,loop=None):
    q = asyncio.Queue(loop=loop)
    self.observers.append(q)
    return q

  def _start_module(self):
    self.pipe = self.module.start()
    procdb_client.update_module(self.module)
    if self.pipe is None:
      logging.error("Cannot start module [%s]"%self.module)
      return False
    
  async def run(self,restart=True):
    cmd = shlex.split(self.module.exec_path)
    create =asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE,
                                             stderr=asyncio.subprocess.PIPE)
    try:
      proc = await create
    except Exception as e:
      self.procdb_client.log_to_module("ERROR: cannot start module: \n\t%s"%e,
                                       self.module.id)
      logging.error("Cannot start module [%s]"%self.module)
      return
    self.module.status = inputmodule.STATUS_RUNNING
    self.module.pid = proc.pid
    self.procdb_client.update_module(self.module)
    self.procdb_client.log_to_module("---starting module---",self.module.id)
    
    npipe = numpypipe.NumpyPipe(proc.stdout, num_cols = self.module.numpy_columns())
    asyncio.ensure_future(self._logger(proc.stderr))
    async for block in npipe:
      for q in self.observers:
        q.put_nowait(block)
    await proc.wait()
    #---only gets here if process terminates---
    if(restart):
      logging.error("Restarting failed module: %s"%self.module)
      #insert an empty block in observers to indicate end of interval
      for q in self.observers:
        q.put_nowait(None)
      asyncio.ensure_future(self.run())

  async def _logger(self,stream):
    while(not stream.at_eof()):
      bline = await stream.readline()
      line = bline.decode('UTF-8').rstrip()
      self.procdb_client.log_to_module(self.module.id,line)
"""
  if(self._start_module()==False):
      return
    
      try:
        with self.pipe.open():
          while(self.run):
            block = self.pipe.get()
            for out_queue in self.observers:
              out_queue.put(block)
      except numpypipe.PipeEmpty:
        if(not self.module.is_alive()):
          logging.error("Restarting failed module: %s"%self.module)
          if(self._start_module()==False):
            return

          for out_queue in self.observers:
              out_queue.put(None)

          
 """     
      
