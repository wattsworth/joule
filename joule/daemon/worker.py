import threading

from joule.procdb import client as procdb_client
import logging
import queue

class Worker(threading.Thread):

  def __init__(self,module,module_timeout=3):
    super().__init__()
    self.observers = []
    self.process = None
    self.module = module
    #if no data comes within module_timeout, check process status
    self.module_timeout = module_timeout
    
  def subscribe(self,queue):
    self.observers.append(queue)

  def stop(self):
    self.run = False
    self.module.stop()
  
  def run(self):
    pipe = self.module.start()
    procdb_client.update_module(self.module)
    while(self.run):
      try:
        with pipe.open():
          while(self.run):
            block = pipe.get()
            for out_queue in self.observers:
              out_queue.put(block)
      except queue.Empty:
        if(not self.module.is_alive()):
          pipe = self.module.restart()
          logging.error("Restarting failed module: %s"%self.module)
          
        
      
