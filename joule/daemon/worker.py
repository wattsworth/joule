import logging
import asyncio
import shlex
from . import inputmodule
from joule.utils import numpypipe


class Worker:

  def __init__(self,module,procdb_client):
    self.observers = []
    self.module = module
    self.procdb_client = procdb_client
    
  def subscribe(self,loop=None):
    q = asyncio.Queue(loop=loop)
    self.observers.append(q)
    return q
    
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
