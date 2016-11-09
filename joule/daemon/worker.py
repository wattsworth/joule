import logging
import asyncio
import shlex
from . import inputmodule
from joule.utils import numpypipe


class Worker:

  def __init__(self,module,procdb_client):
    self.observers = []
    self.module = module
    self.inputs = {} #no inputs
    for path in self.module.source_paths:
      #add the path as an input
      self.inputs[path]=None

    self.procdb_client = procdb_client
    self.process = None
    self.stop_requested = False
    self.all_inputs_registered = False
    
  def subscribe(self,loop=None):
    q = asyncio.Queue(loop=loop)
    self.observers.append(q)
    return q

  def register_inputs(self,worked_paths):
    #check if all the module's inputs are available
    missing_input = False
    for path in self.inputs.keys():
      if not path in worked_paths:
        missing_input = True
    if(missing_input):
      return False #cannot find all input sources
    #subscribe to inputs
    for path in self.inputs.keys():
      self.inputs[path] = worked_paths[path].subscribe()
    return True
  
  def _validate_inputs(self):
    for key,value in self.inputs:
      if value is None:
        logging.error("Cannot start module [{name}]: no input source for [{path}]".\
                      format(name=self.module,path=key))
        return False
    return True
  
  async def run(self,restart=True,loop=None):
    if(not self._validate_inputs()):
      return
    self.stop_requested = False
    while(True):
      await self._run_once(loop)
      #---only gets here if process terminates---
      if(restart and not self.stop_requested):
        logging.error("Restarting failed module: %s"%self.module)
        await asyncio.sleep(0.1)
        #insert an empty block in observers to indicate end of interval
        for q in self.observers:
          q.put_nowait(None)
      else:
        break

    
  async def _run_once(self,loop=None):
    cmd = shlex.split(self.module.exec_cmd)
    create = asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE,
                                             stderr=asyncio.subprocess.PIPE)
    try:
      self.process = await create
    except Exception as e:
      self.procdb_client.log_to_module("ERROR: cannot start module: \n\t%s"%e,
                                       self.module.id)
      logging.error("Cannot start module [%s]"%self.module)
      self.process = None
      return

    self.module.status = inputmodule.STATUS_RUNNING
    self.module.pid = self.process.pid
    self.procdb_client.update_module(self.module)
    self.procdb_client.log_to_module("---starting module---",self.module.id)
    
    npipe = numpypipe.NumpyPipe(self.process.stdout,
                                num_cols = self.module.numpy_columns())
    self.logger_task = asyncio.ensure_future(self._logger(self.process.stderr),loop=loop)
    async for block in npipe:
      for q in self.observers:
        q.put_nowait(block)
    await self.process.wait()
    self.process = None
    
  async def stop(self,loop):

    self.stop_requested = True
    if(self.process is None):
      return

    self.process.terminate()
    try:
      await asyncio.wait_for(self.process.wait(),timeout=2,loop=loop)
    except asyncio.TimeoutError:
      self.process.kill()
    await self.logger_task

    
  async def _logger(self,stream):
    while(True):
      bline = await stream.readline()
      if(len(bline)==0):
        break
      line = bline.decode('UTF-8').rstrip()
      self.procdb_client.log_to_module(self.module.id,line)
