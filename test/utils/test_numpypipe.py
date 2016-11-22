
import asynctest
from joule.utils import numpypipe
import os
import numpy as np
import asyncio
from . import helpers

class TestNumpyPipe(asynctest.TestCase):

  def test_pipes_numpy_arrays(self):  
    (fd_r,fd_w) = os.pipe()
    loop = asyncio.get_event_loop()
    #wrap the file descriptors in numpypipes
    my_stream = helpers.build_stream(name="test",num_elements=8)
    npipe_in = numpypipe.NumpyPipe(fd_w,my_stream,loop)
    npipe_out = numpypipe.NumpyPipe(fd_r,my_stream,loop)
    input_data = helpers.create_data(my_stream)

    
    async def putter():
      NUM_BLOCKS=4
      for n in range(NUM_BLOCKS):
        block_size = len(input_data)//NUM_BLOCKS
        #make sure the data is evenly divided into blocks
        self.assertEqual(block_size*NUM_BLOCKS,len(input_data))
        block = input_data[n*block_size:(n+1)*block_size]
        #write the block to the pipe
        await npipe_in.write(block)
        await asyncio.sleep(0.01)
      os.close(fd_w)

      
    async def getter():
      run_count = 0
      while(True):
        try:
          block = await npipe_out.read()
        except numpypipe.PipeClosed:
          break
        if run_count == 0:
          output_data = block
        else:
          output_data = np.vstack((output_data,block))
        run_count+=1
      #make sure the reads are broken up (otherwise test is lame...)
      self.assertGreater(run_count,2)
      #and make sure we got the right data out
      np.testing.assert_array_equal(input_data,output_data)

    tasks = [asyncio.ensure_future(putter()),
             asyncio.ensure_future(getter())]
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.gather(*tasks))

    npipe_in.close()
    npipe_out.close()
    #make sure the numpy array made it through the pipe

  def test_reconstructs_fragmented_data(self):
    (fd_r,fd_w) = os.pipe()
    loop = asyncio.get_event_loop()
    my_stream = helpers.build_stream(name="test",num_elements=2)
    my_numpypipe = numpypipe.NumpyPipe(fd_r,my_stream,loop)

    input_data = helpers.create_data(my_stream)

    async def putter():
      b_data = input_data.tobytes()
      f = open(fd_w,'wb',0)
      f.write(b_data[:100])
      await asyncio.sleep(0.05)
      f.write(b_data[100:201])
      await asyncio.sleep(0.05)
      f.write(b_data[201:])
      f.close()
      
    async def getter():
      run_count = 0
      while(True):
        try:
          block = await my_numpypipe.read()
        except numpypipe.PipeClosed:
          break
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

