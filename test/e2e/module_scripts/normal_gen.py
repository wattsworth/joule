#!/usr/bin/python3

from nilmdb.utils.time import now as time_now
import time
from joule.utils.fdnumpypipe import FdNumpyPipe
import numpy as np
import argparse
import json
import asyncio

rows = 100
freq = 4 #Hz

  
async def main(ts,pipe):
  data = 100*np.sin(np.arange(0,2*np.pi,2*np.pi/rows))
  data.shape=(rows,1)
  ts_inc = 1/rows*(1/freq)*1e6 #microseconds
  data_ts = ts
  np_out = FdNumpyPipe("np_out",layout=pipe['layout'],fd=pipe['fd'])
  while(True):
    top_ts = data_ts+100*ts_inc
    ts = np.array(np.linspace(data_ts,top_ts,rows,endpoint=False), dtype=np.uint64)
    ts.shape = (rows,1)
    ts_data = np.hstack((ts,data))
    await np_out.write(ts_data)
    print("added data")
    data_ts = top_ts
    time.sleep(1/freq)

if __name__=="__main__":
  print("starting!")
  parser = argparse.ArgumentParser()
  parser.add_argument("--pipes")
  args = parser.parse_args()
  pipes = json.loads(args.pipes)
  pipe_out = pipes["destinations"]["path1"]

  loop = asyncio.get_event_loop()
  loop.run_until_complete(main(time_now(),pipe_out))
  loop.close()
  
