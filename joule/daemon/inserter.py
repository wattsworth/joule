import numpy as np
import queue

class NilmDbInserter:
  def __init__(self,client,path,decimate=True):
    self.decimate = decimate
    self.path = path
    self.inserter = client.stream_insert_numpy_context(path).__enter__()
    self.queue = queue.Queue()
    self.buffer = None
    
  def process_data(self):
    while not self.queue.empty():
      data = self.queue.get()
      if(data is None):
        self.flush()
        self.inserter.finalize()
      elif(self.buffer is None):
        self.buffer = np.array(data)
      else:
        self.buffer = np.append(self.buffer,data,axis=0)
    self.flush()
    
  def flush(self):
    if(self.buffer is None or len(self.buffer) == 0):
      return #nothing to flush
    self.inserter.insert(self.buffer)
    if(self.decimate):
      self.decimator.process(self.data)

  def finalize(self):
    self.inserter.finalize()

class NilmDbDecimator:
  def __init__(self,client,path,level,factor=4,again=False):
    self.again = again
    self.level = level
    self.factor = factor
    self.path = "{path}~decim-{level}".format(path=path,level=level)
    res = client.stream_list(path = self.path)
    if(len(res)==0):
      #create the stream
      client.stream_create(self.path,"float32_{width}".format(width=width*3))
    self.inserter = client.stream_insert_numpy_context(path).__enter__()

  def process(self,data):
    pass #insert decimated data
