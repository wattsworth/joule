import numpy as np
import asyncio
import re
from .errors import DaemonError

class NilmDbInserter:
  def __init__(self,client,
               path,
               insertion_period=0, #no insertion buffering by default
               decimate=True):
    if(decimate):
      self.decimator = NilmDbDecimator(client,path)
    else:
      self.decimator = None

    self.insertion_period=insertion_period
    self.path = path
    self.client = client
    self.last_ts = None
    self.buffer = None
    self.stop_requested = False
    
  async def process(self,queue,loop=None):
    while(not self.stop_requested):
      await asyncio.sleep(self.insertion_period,loop=loop)
      while not queue.empty():
        data = await queue.get()
        if(data is None):
          self.flush()
          self.finalize()
        elif(self.buffer is None):
          self.buffer = np.array(data)
        else:
          self.buffer = np.append(self.buffer,data,axis=0)
      self.flush()

  def stop(self):
    self.stop_requested = True
    
  def flush(self):
    if(self.buffer is None or len(self.buffer) == 0):
      return #nothing to flush
    if(self.last_ts is None):
      self.last_ts = self.buffer[0,0]

    start = self.last_ts
    end = self.buffer[-1,0]+1
    self.client.stream_insert_numpy(self.path, self.buffer,
                                    start=start, 
                                    end=end)
    self.last_ts = end #append next buffer to this interval
    if(self.decimator is not None):
      self.decimator.process(self.buffer)
    self.buffer = None
    
  def finalize(self):
    self.last_ts = None
    if(self.decimator is not None):
      self.decimator.finalize()

class NilmDbDecimator:
  def __init__(self,client,source_path,factor=4):
    self.factor = factor
    self.client = client
    #get source info
    try:
      _,source_layout=client.stream_list(path = source_path)[0]
    except IndexError:
      raise DaemonError("the decimator source [{path}] is not in the database".\
                        format(path=source_path))
    if(self._is_decimated(source_path)):
      destination_layout = source_layout
      self.again = True
      (base_path,source_level) = self._parse_path(source_path)
      level = source_level*factor
    else:
      self.again = False
      destination_layout = "float32_{width}".\
                           format(width=self._stream_width(source_layout)*3)
      base_path = source_path
      level = factor
    destination_path = "{base}~decim-{level}".format(base=base_path,level=level)

    #create the destination if it doesn't exist
    if(len(client.stream_list(destination_path))==0):
      client.stream_create(destination_path,destination_layout)
    
    self.last_ts = None
    self.buffer = []
    self.child = None
    self.path = destination_path
    
  def _parse_path(self,path):
    """return the base path and the decimation level"""
    res = re.search("^([/\w]*)~decim-(\d*)$",path)
    #this function is only called if the source path is decimated
    #so it is garaunteed to match this regex, implicitly raise an error o.w.
    return [res.group(1),int(res.group(2))]
    
  def _is_decimated(self,path):
    if(re.search("~decim-\d*$",path) is not None):
      return True

  def _stream_width(self,layout):
    res = re.search("\_(\d*)$",layout)
    if(res is None):
      raise DaemonError("invalid layout: %s"%layout)
    return int(res.group(1))

  def finalize(self):
    self.buffer = []
    self.last_ts = None
    if(self.child is not None):
      self.child.finalize()
      
  def process(self,data):
    #check if there is old data
    if(len(self.buffer) != 0):
      #append the new data onto the old data
      data = np.concatenate((self.buffer,data))
    (n, m) = data.shape

    # Figure out which columns to use as the source for mean, min, and max,
    # depending on whether this is the first decimation or we're decimating
    # again.  Note that we include the timestamp in the means.
    if self.again:
      c = (m - 1) // 3
      # e.g. c = 3
      # ts mean1 mean2 mean3 min1 min2 min3 max1 max2 max3
      mean_col = slice(0, c + 1)
      min_col = slice(c + 1, 2 * c + 1)
      max_col = slice(2 * c + 1, 3 * c + 1)
    else:
      mean_col = slice(0, m)
      min_col = slice(1, m)
      max_col = slice(1, m)

    # Discard extra rows that aren't a multiple of factor
    n = n // self.factor * self.factor

    if(n==0): #not enough data to work with, save it for later
      self.buffer = data
      return

    trunc_data = data[:n,:]
    # keep the leftover data
    self.buffer=np.copy(data[n:,:])

    # Reshape it into 3D so we can process 'factor' rows at a time
    trunc_data = trunc_data.reshape(n // self.factor, self.factor, m)

    # Fill the result
    out = np.c_[ np.mean(trunc_data[:,:,mean_col], axis=1),
                     np.min(trunc_data[:,:,min_col], axis=1),
                     np.max(trunc_data[:,:,max_col], axis=1) ]

    # set up the interval
    if(self.last_ts is None):
      self.last_ts = data[0,0]

    start = self.last_ts
    end = data[n-1,0]+1
    # insert the data into the database
    self.client.stream_insert_numpy(self.path, out,
                                    start=start, 
                                    end=end)
    self.last_ts = end
    # now call the child decimation object
    if(self.child==None):
      self.child = NilmDbDecimator(self.client,self.path)
    self.child.process(out)

