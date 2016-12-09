#!/usr/bin/python3
"""
InStream1 ==> x2 ==> InStream2
InStream2 ==> x3 ==> OutStream2
"""

import asyncio
import json
import argparse
from joule.utils.fdnumpypipe import FdNumpyPipe
import sys

async def echo_pipe(np_in,np_out,factor=1.0):
  while(True):
    data = await np_in.read(flatten=True)
    data[:,1:]*=factor
    await np_out.write(data)

if __name__=="__main__":
  sys.stderr.write("starting filter!\n")
  sys.stderr.flush()
  parser = argparse.ArgumentParser("demo")
  parser.add_argument("--pipes")
  args = parser.parse_args()

  pipe_args = json.loads(args.pipes)

  loop = asyncio.get_event_loop()

  pipe_in1 = pipe_args['sources']['path1']
  pipe_out1 = pipe_args['destinations']['path1']  
  np_in1 = FdNumpyPipe("np_in1",layout=pipe_in1['layout'],
                       fd = pipe_in1['fd'])
  np_out1 = FdNumpyPipe("np_out1",layout=pipe_out1['layout'],
                        fd = pipe_out1['fd'])
  
  pipe_in2 = pipe_args['sources']['path2']
  pipe_out2 = pipe_args['destinations']['path2']  
  np_in2 = FdNumpyPipe("np_in2",layout=pipe_in2['layout'],
                       fd = pipe_in2['fd'])
  np_out2 = FdNumpyPipe("np_out2",layout=pipe_out2['layout'],
                        fd = pipe_out2['fd'])

  tasks = [
    asyncio.ensure_future(echo_pipe(np_in1,np_out1,factor=2)),
    asyncio.ensure_future(echo_pipe(np_in2,np_out2,factor=3))]


  loop.run_until_complete(asyncio.gather(*tasks))
  loop.close()
  print("all done")
  
    

