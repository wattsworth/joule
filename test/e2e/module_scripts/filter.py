#!/usr/bin/python3
"""
InStream1 ==> x2 ==> InStream2
InStream2 ==> x3 ==> OutStream2
"""

import asyncio
import json
from joule.procdb import client
from joule.utils import config_manager
import argparse
from joule.utils import numpypipe
import sys

async def echo_pipe(np_in,np_out,factor=1.0):
  while(True):
    data = await np_in.read()
    data[:,1:]*=factor
    await np_out.write(data)

if __name__=="__main__":
  sys.stderr.write("starting filter!\n")
  sys.stderr.flush()
  parser = argparse.ArgumentParser("demo")
  parser.add_argument("--pipes")
  args = parser.parse_args()

  pipe_args = json.loads(args.pipes)

  configs = config_manager.load_configs()
  procdb_client = client.SQLClient(configs.procdb.db_path)

  loop = asyncio.get_event_loop()

  stream1 = procdb_client.find_stream_by_path("/normal1/data")
  assert(stream1 is not None)
  fd1_in = pipe_args['sources']['path1']
  fd1_out = pipe_args['destinations']['path1']  
  np1_in = numpypipe.NumpyPipe(fd1_in,stream1,loop)
  np1_out = numpypipe.NumpyPipe(fd1_out,stream1,loop) #hack, b/c same datatype
  
  stream2 = procdb_client.find_stream_by_path("/normal2/subpath/data")
  assert(stream2 is not None)  
  fd2_in = pipe_args['sources']['path2']
  fd2_out = pipe_args['destinations']['path2']
  np2_in = numpypipe.NumpyPipe(fd2_in,stream2,loop)
  np2_out = numpypipe.NumpyPipe(fd2_out,stream2,loop) #hack, b/c same datatype

  tasks = [
    asyncio.ensure_future(echo_pipe(np1_in,np1_out,factor=2.0)),
    asyncio.ensure_future(echo_pipe(np2_in,np2_out,factor=3.0))]


  loop.run_until_complete(asyncio.gather(*tasks))
  loop.close()
  print("all done")
  
    

