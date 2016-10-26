import threading

from joule.procdb import client as procdb_client
import logging
from joule.utils import numpypipe

class Worker(threading.Thread):

  def __init__(self,module,module_timeout=3):
    super().__init__()
    self.observers = []
    self.process = None
    self.pipe = None
    self.module = module
    #if no data comes within module_timeout, check process status
    self.module_timeout = module_timeout
    
  def subscribe(self,queue):
    self.observers.append(queue)

  def stop(self):
    self.run = False
    self.module.stop()

  def _start_module(self):
    self.pipe = self.module.start()
    procdb_client.update_module(self.module)
    if self.pipe is None:
      logging.error("Cannot start module [%s]"%self.module)
      return False
    
  def run(self):
    if(self._start_module()==False):
      return
    
    while(self.run):
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

          
        
      
