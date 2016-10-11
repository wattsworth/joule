import threading
import multiprocessing as mp

class Worker(threading.Thread):

  def __init__(self,module):
    self.observers = []
    self.q_out = mp.Queue()
    self.process = None

  def subscribe(self,queue):
    self.observers.append(queue)

  def stop(self):
    self.run = False
    self.process.terminate()
  
  def run(self):
    self.process = self.module.start(self.q_out)
    procdb_client.update_module(module)
    while(self.run):
      try:
        while(True):
          block = self.q_out.get()
          for queue in self.observers:
            queue.put(block)
      except QueueClosed:
        self.q_out = mp.Queue()
        self.process = self.module.start(self.q_out)
        logger.error("Module restarted")
        
      
