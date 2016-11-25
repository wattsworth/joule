#!/usr/bin/python3

from nilmdb.utils.time import now as time_now
import time
import numpy as np
import argparse
import json

rows = 100
freq = 4 #Hz

  
def main(ts,fd):
  data = np.sin(np.arange(0,2*np.pi,2*np.pi/rows))
  data.shape=(rows,1)
  ts_inc = 1/rows*(1/freq)*1e6 #microseconds
  data_ts = ts
  output = open(fd,'wb')
  while(True):
    top_ts = data_ts+100*ts_inc
    ts = np.array(np.linspace(data_ts,top_ts,rows,endpoint=False), dtype=np.uint64)
    ts.shape = (rows,1)
    ts_data = np.hstack((ts,data))
    output.write(ts_data.tobytes())
    print("added data")
    data_ts = top_ts
    time.sleep(1/freq)

if __name__=="__main__":
  print("starting!")
  parser = argparse.ArgumentParser()
  parser.add_argument("--pipes")
  args = parser.parse_args()
  pipes = json.loads(args.pipes)
  output_fd = pipes["destinations"]["path1"]
  main(time_now(),output_fd)
  
