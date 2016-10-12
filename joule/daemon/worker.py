import threading
import queue
import multiprocessing as mp
from joule.procdb import client as procdb_client
import logging

class Worker(threading.Thread):

  def __init__(self,module,module_timeout=3):
    super().__init__()
    self.observers = []
    self.q_out = mp.Queue()
    self.process = None
    self.module = module
    #if no data comes within module_timeout, check process status
    self.module_timeout = module_timeout
    
  def subscribe(self,queue):
    self.observers.append(queue)

  def stop(self):
    self.run = False
    self.process.terminate()
  
  def run(self):
    self.process = self.module.start(self.q_out)
    procdb_client.update_module(self.module)
    while(self.run):
      try:
        block = self.q_out.get(timeout=self.module_timeout)
        for out_queue in self.observers:
          out_queue.put(block)
      except queue.Empty:
        if(self.process.is_alive()==False):
          self.q_out = mp.Queue()
          self.process = self.module.start(self.q_out)
          logging.error("Module [{module}] restarted".format(module=self.module))
        
      
