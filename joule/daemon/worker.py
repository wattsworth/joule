import logging
import asyncio
import shlex
from joule.daemon import module
from joule.utils import numpypipe
import os
import json

class Worker:

  def __init__(self,my_module,procdb_client):

    self.module = my_module
    self.output_queues = {}
    self.input_queues = {} #no inputs
    
    for path in self.module.destination_paths.values():
      #add output_queues for each destination
      self.output_queues[path] = []

    for path in self.module.source_paths.values():
      #add the path as an input
      self.input_queues[path]=None

    self.procdb_client = procdb_client
    self.process = None
    self.stop_requested = False
    self.npipes = []
    self.child_pipes = {
      'destinations': {},
      'sources': {}
    }
    self.pipe_tasks = []

    #tunable constants
    self.SIGTERM_TIMEOUT = 2 #how long to wait for proc to stop nicely
    self.RESTART_INTERVAL = 1 #how long to wait to restart a failed process
    
  def subscribe(self,path,loop=None):
    q = asyncio.Queue(loop=loop)
    self.output_queues[path].append(q)
    return q

  def register_inputs(self,worked_paths):
    #check if all the module's inputs are available
    missing_input = False
    for path in self.input_queues.keys():
      if not path in worked_paths:
        missing_input = True
    if(missing_input):
      return False #cannot find all input sources
    #subscribe to inputs
    for path in self.input_queues:
      self.input_queues[path] = worked_paths[path].subscribe()
    return True
  
  def _validate_inputs(self):
    for key,value in self.input_queues.items():
      if value is None:
        logging.error("Cannot start {module}: no input source for [{path}]".\
                      format(module=self.module,path=key))
        return False
    return True
  
  async def run(self,restart=True,loop=None):
    if(not self._validate_inputs()):
      return
    if(loop==None):
      loop = asyncio.get_event_loop()
    self.stop_requested = False
    while(True):
      await self._run_once(loop)
      #---only gets here if process terminates---
      if(restart and not self.stop_requested):
        logging.error("Restarting failed module: %s"%self.module)
        await asyncio.sleep(self.RESTART_INTERVAL)
        #insert an empty block in output_queues to indicate end of interval
        for queue_set in self.output_queues.values():
          for q in queue_set:
            q.put_nowait(None)
      else:
        break

    
  async def _run_once(self,loop):

    cmd = shlex.split(self.module.exec_cmd)
    await self._start_pipe_tasks(loop)
    cmd+=["--pipes",json.dumps(self.child_pipes)]
    create = asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE,
                                             stderr=asyncio.subprocess.STDOUT, close_fds=False)
    try:
      self.process = await create
    except Exception as e:
      self.procdb_client.add_log_by_module("ERROR: cannot start module: \n\t%s"%e,
                                       self.module.id)
      logging.error("Cannot start %s"%self.module)
      self.process = None
      self._close_child_pipes()
      await self._close_npipes()
      return
    self._close_child_pipes()
    self.module.status = module.STATUS_RUNNING
    self.module.pid = self.process.pid
    self.procdb_client.update_module(self.module)
    self.procdb_client.add_log_by_module("---starting module---",self.module.id)
    self.logger_task = asyncio.ensure_future(self._logger(self.process.stdout),loop=loop)

    await self.process.wait()
    self.process = None
    await self._close_npipes()
    
  async def stop(self,loop):
    self.stop_requested = True
    if(self.process is None):
      return

    self.process.terminate()
    try:
      await asyncio.wait_for(self.process.wait(),
                             timeout=self.SIGTERM_TIMEOUT,
                             loop=loop)
    except asyncio.TimeoutError:
      logging.warning("Cannot stop %s with SIGTERM, killing process"%self.module)
      self.process.kill()
    await self.logger_task
    
  async def _logger(self,stream):
    while(True):
      bline = await stream.readline()
      if(len(bline)==0):
        break
      line = bline.decode('UTF-8').rstrip()
      self.procdb_client.add_log_by_module(self.module.id,line)

  async def _start_pipe_tasks(self,loop):
    #configure destination pipes          [module]==>[jouled]
    for name,path in self.module.destination_paths.items():
      (npipe,fd) = self._build_numpy_pipe(path,'output',loop)
      self.child_pipes['destinations'][name]=fd
      self.npipes.append(npipe)
      task = asyncio.ensure_future(self._pipe_in(npipe,self.output_queues[path]))
      self.pipe_tasks.append(task)
    
    #configure source pipes               [jouled]==>[module]
    for name,path in self.module.source_paths.items():
      (fd,npipe) = self._build_numpy_pipe(path,'input',loop)
      self.child_pipes['sources'][name] = fd
      self.npipes.append(npipe)
      task = asyncio.ensure_future(self._pipe_out(self.input_queues[path],npipe))
      self.pipe_tasks.append(task)

  def _build_numpy_pipe(self,path,direction,loop):
    stream = self.procdb_client.find_stream_by_path(path)
    assert(stream is not None) #procdb must have this stream entry
    (r,w) = os.pipe()
    if(direction=='output'): # fd    ==> npipe
      os.set_inheritable(w,True)
      npipe = numpypipe.NumpyPipe(r,stream,loop)
      return(npipe,w)
    else:                    # npipe ==> fd
      os.set_inheritable(r,True)
      npipe = numpypipe.NumpyPipe(w,stream,loop)
      return (r,npipe)
    
  def _close_child_pipes(self):
    for pipe_set in self.child_pipes.values():
      for pipe in pipe_set.values():
        os.close(pipe)
    
  async def _close_npipes(self):
    for npipe in self.npipes:
      npipe.close()
    for task in self.pipe_tasks:
      task.cancel()

      
  async def _pipe_in(self,npipe,queues):
    """given a numpy pipe, get data and put it 
       into each queue in [output_queues] """    
    while(True):
      try:
        data = await npipe.read()
        for q in queues:
          q.put_nowait(data)
      except numpypipe.PipeClosed:
        break
     
  async def _pipe_out(self,queue,npipe):
    while(True):
      data = await queue.get()
      await npipe.write(data)

