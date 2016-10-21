import configparser
import joule.daemon.destination as destination

def parse_configs(config_str):
  config = configparser.ConfigParser()
  config.read_string(config_str)
  return config

def stub_destination(path="",datatype="",keep_us=0,decimate=False):
  """returns a Destination object with default values"""
  return destination.Destination(path,datatype,keep_us,decimate)


  
          
