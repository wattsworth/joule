import configparser
from joule.daemon import stream,element
import numpy as np

def build_stream(name,
                 description="test_description",
                 path="/some/path/to/data",
                 datatype="float32",
                 keep_us=0,
                 decimate = True,
                 id=None,
                 num_elements = 0):
  my_stream =  stream.Stream(name,description,path,datatype,keep_us,decimate,id)
  for n in range(num_elements):
    my_stream.add_element(element.build_element("e%d"%n))
  return my_stream

def create_data(layout,
                length=100,
                step=1000,            #in us
                start=1476152086000): #10 Oct 2016 10:15PM
  

  """Create a random block of NilmDB data with [layout] structure"""
  ts = np.arange(start,start+step*length,step,dtype=np.uint64)

  # Convert to structured array
  (ltype,lcount,dtype) = parse_layout(layout)
  sarray = np.zeros(len(ts), dtype=dtype)
  if("float" in ltype):
    data = np.random.rand(length,lcount)
  elif("uint" in ltype):
    data = np.random.randint(0,high=100,size=(length,lcount),dtype=dtype[1].base)
  else:
    data = np.random.randint(-50,high=50,size=(length,lcount),dtype=dtype[1].base)

  sarray['timestamp'] = ts
  # Need the squeeze in case sarray['data'] is 1 dimensional
  sarray['data'] = np.squeeze(data)
  return sarray

def parse_layout(layout):
  ltype = layout.split('_')[0]
  lcount = int(layout.split('_')[1])
  if ltype.startswith('int'):
      atype = '<i' + str(int(ltype[3:]) // 8)
  elif ltype.startswith('uint'):
      atype = '<u' + str(int(ltype[4:]) // 8)
  elif ltype.startswith('float'):
      atype = '<f' + str(int(ltype[5:]) // 8)
  else:
      raise ValueError("bad layout")
  dtype = np.dtype([('timestamp', '<i8'), ('data', atype, lcount)])
  return (ltype,lcount,dtype)

  
def parse_configs(config_str):
  config = configparser.ConfigParser()
  config.read_string(config_str)
  return config

default_config = parse_configs(
      """
        [NilmDB]:
          URL = http://localhost/nilmdb
          InsertionPeriod = 5
        [ProcDB]:
          DbPath = /tmp/joule-proc-db.sqlite
          MaxLogLines = 100
        [Jouled]:
          ModuleDirectory = /etc/joule/module_configs
          StreamDirectory = /etc/joule/stream_configs
    """)
