import logging
import asyncio
import shlex
from . import inputmodule
from joule.utils import numpypipe
import os
import json

class Worker:

  def __init__(self,module,procdb_client):
    self.observers = {}
    for path in self.module.destination_paths.values():
      #add observer queues for each destination
      self.observers[path] = []
    self.observers = []
    self.module = module
    self.input_queues = {} #no inputs
    for path in self.module.source_paths.values():
      #add the path as an input
      self.input_queues[path]=None

    self.procdb_client = procdb_client
    self.process = None
    self.stop_requested = False
    self.pipe_transports = []
    self.child_pipes = []
    self.pipe_tasks = []
    
  def subscribe(self,path,loop=None):
    q = asyncio.Queue(loop=loop)
    self.observers[path].append(q)
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
        logging.error("Cannot start module [{name}]: no input source for [{path}]".\
                      format(name=self.module,path=key))
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
        await asyncio.sleep(0.1)
        #insert an empty block in observers to indicate end of interval
        for q in self.observers:
          q.put_nowait(None)
      else:
        break

    
  async def _run_once(self,loop):

    cmd = shlex.split(self.module.exec_cmd)
    pipes = await self._start_pipe_tasks(loop)
    cmd+=["--pipes",json.dumps(pipes)]
    create = asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE,
                                             stderr=asyncio.subprocess.STDOUT, close_fds=False)
    try:
      self.process = await create
    except Exception as e:
      self.procdb_client.log_to_module("ERROR: cannot start module: \n\t%s"%e,
                                       self.module.id)
      logging.error("Cannot start module [%s]"%self.module)
      self.process = None
      self._close_child_pipes()
      self._stop_pipe_tasks()
      return
    self._close_child_pipes()
    self.module.status = inputmodule.STATUS_RUNNING
    self.module.pid = self.process.pid
    self.procdb_client.update_module(self.module)
    self.procdb_client.log_to_module("---starting module---",self.module.id)
    self.logger_task = asyncio.ensure_future(self._logger(self.process.stdout),loop=loop)

    await self.process.wait()
    self.process = None
    self._stop_pipe_tasks()
    
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

  async def _start_pipe_tasks(self,loop):
    pipes = {
      'destination': 0,
      'sources': {}
    }

    #configure destination pipes (output)
    for name,path in self.module.destination_paths.items():
      (dest_r,dest_w) = os.pipe()
      os.set_inheritable(dest_w,True)
      self.child_pipes.append(dest_w)
      task = await self._start_stream_reader(dest_r,self.observers[path],loop)
      pipes['destination'][name]=dest_w
      self.pipe_tasks.append(task)
    
    #configure source pipes (input)
    for name,path in self.module.source_paths.items():
      (source_r,source_w) = os.pipe()
      os.set_inheritable(source_r,True)
      self.child_pipes.append(source_r)
      task = await self._start_stream_writer(self.input_queues[path],source_w,loop)
      pipes['sources'][name] = source_r
      self.pipe_tasks.append(task)
      
    return pipes

  async def _start_stream_reader(self,fd,loop):
    reader = asyncio.StreamReader()
    reader_protocol = asyncio.StreamReaderProtocol(reader)
    f = open(fd,'rb')
    (transport,_) = await loop.connect_read_pipe(lambda: reader_protocol, f)
    self.pipe_transports.append(transport)
    return asyncio.ensure_future(self._pipe_in(reader))


  async def _start_stream_writer(self,queue,fd,loop):
    write_protocol = asyncio.StreamReaderProtocol(asyncio.StreamReader())
    f = open(fd,'wb')
    write_transport, _ = await loop.connect_write_pipe(
      lambda: write_protocol, f)
    writer = asyncio.StreamWriter(write_transport, write_protocol, None, loop)
    self.pipe_transports.append(write_transport)
    return asyncio.ensure_future(self._pipe_out(queue,writer))

  def _close_child_pipes(self):
    for pipe in self.child_pipes:
      os.close(pipe)
    self.child_pipes = []
    
  def _stop_pipe_tasks(self):
    for transport in self.pipe_transports:
      transport.close()
    self.pipe_transports = []
    for task in self.pipe_tasks:
      task.cancel()
    self.pipe_tasks = []

  async def _pipe_in(self,reader,queues):
    
    npipe = numpypipe.NumpyPipe(reader,
                                num_cols = self.module.numpy_columns())
    async for block in npipe:
      for q in queues:
        q.put_nowait(block)
     
  async def _pipe_out(self,queue,writer):
    while(True):
      data = await queue.get()
      writer.write(data.tobytes())
        
