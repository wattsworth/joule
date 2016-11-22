import configparser
from joule.daemon import stream,module,element
import numpy as np

def parse_configs(config_str):
  config = configparser.ConfigParser()
  config.read_string(config_str)
  return config

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

def build_module(name,
                 description ="test_description",
                 exec_cmd="/bin/true",
                 source_paths = {"path1":"/some/path/1"},
                 destination_paths = {"path1":"/some/path/2"},
                 status=module.STATUS_UNKNOWN,
                 pid=-1,
                 id=None):
  return module.Module(name,description,exec_cmd,source_paths,destination_paths,
                       status=status,pid=pid,id=id)

def create_data(stream,
                length=100,
                step=1000,            #in us
                start=1476152086000): #10 Oct 2016 10:15PM
  

  """Create a random block of NilmDB data [ts, stream]"""
  ts = np.arange(start,start+step*length,step,dtype=np.uint64)
  data = np.random.rand(length,len(stream.elements))
  return np.hstack((ts[:,None],data))
