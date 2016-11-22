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

def create_data(stream,
                length=100,
                step=1000,            #in us
                start=1476152086000): #10 Oct 2016 10:15PM
  

  """Create a random block of NilmDB data [ts, stream]"""
  ts = np.arange(start,start+step*length,step,dtype=np.uint64)
  data = np.random.rand(length,len(stream.elements))
  return np.hstack((ts[:,None],data))


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
