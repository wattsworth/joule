
import nilmdb.client
import requests

NILMDB_URL = "http://localhost/nilmdb"

def intervals(path):
  client = _get_client()
  intervals =client.stream_intervals(path)
  return list(intervals)

def data_count(path,interval=None):
  if(interval is None):
    req = requests.get("{url}/stream/extract?path={path}&count=1".format(url=NILMDB_URL,path=path))
  else:
    req = requests.get("{url}/stream/extract?path={path}&start={start}&end={end}&count=1".format(url=NILMDB_URL,path=path,start=interval[0],end=interval[1]))

  return int(req.text)
    



def is_decimated(path,level=16,min_size=10):
  dec_path = path+"~decim-%d"%level
  req = requests.get("{url}/stream/extract?path={path}&count=1".format(url=NILMDB_URL,path=dec_path))
  return int(req.text)>min_size
  
def _get_client():
  return nilmdb.client.client.Client(NILMDB_URL)  
