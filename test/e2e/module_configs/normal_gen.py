#!/usr/bin/python3

from nilmdb.utils.time import now as time_now
import time
import numpy as np
import sys,os
rows = 100
freq = 4 #Hz

  
def main(ts):
  data = np.sin(np.arange(0,2*np.pi,2*np.pi/rows))
  data.shape=(rows,1)
  ts_inc = 1/rows*(1/freq)
  data_ts = ts
  while(True):
    top_ts = data_ts+100*ts_inc
    ts = np.array(np.linspace(data_ts,top_ts,rows,endpoint=False), dtype=np.uint64)
    ts.shape = (rows,1)
    
    print(data.shape)
    print(ts.shape)
    ts_data = np.hstack((ts,data))

    os.write(sys.stdout.fileno(),ts_data.tobytes())
    data_ts = top_ts
    time.sleep(1/freq)

if __name__=="__main__":
  main(time_now())
  
