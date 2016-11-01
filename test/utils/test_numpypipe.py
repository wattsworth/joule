
import asynctest
from joule.utils.numpypipe import NumpyPipe
import os
import numpy as np
import asyncio

class TestNumpyPipe(asynctest.TestCase):

  def test_passes_numpy_data(self):
    """constructs numpy arrays from blocks of bytes"""
    stream = asyncio.StreamReader()
    my_numpypipe = NumpyPipe(stream,3)

    input_data = self._create_data(length=100,
                                   streams=2)

    async def putter():
      b_data = input_data.tobytes()
      stream.feed_data(b_data[:100])
      await asyncio.sleep(0.05)
      stream.feed_data(b_data[100:201])
      await asyncio.sleep(0.05)
      stream.feed_data(b_data[201:])

      stream.feed_eof()
      
    async def getter():
      run_count = 0
      async for block in my_numpypipe:
        if run_count == 0:
          output_data = block
        else:
          output_data = np.vstack((output_data,block))
        run_count+=1
      #make sure the byte reads are broken up
      self.assertGreater(run_count,2)
      #and make sure we got the right data out 
      np.testing.assert_array_equal(input_data,output_data)
      
    tasks = [asyncio.ensure_future(putter()),
             asyncio.ensure_future(getter())]
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.gather(*tasks))
    
  def _create_data(timestamped=True,
                     length=100,
                     streams=1):
    start=1476152086000 #10 Oct 2016 10:15PM
    step = 1000
    """Create a random block of NilmDB data [ts, stream]"""
    ts = np.arange(start,start+step*length,step,dtype=np.uint64)
    data = np.random.rand(length,streams)
    return np.hstack((ts[:,None],data))
