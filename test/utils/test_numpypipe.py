
import asynctest
from joule.utils.fdnumpypipe import FdNumpyPipe
import os
import numpy as np
import asyncio
from . import helpers

class TestFdNumpyPipe(asynctest.TestCase):

  def test_pipes_numpy_arrays(self):
    LAYOUT="int8_2"; LENGTH=1000
    (fd_r,fd_w) = os.pipe()

    #wrap the file descriptors in numpypipes
    npipe_in = FdNumpyPipe("pipe_in",fd_w,layout=LAYOUT)
    npipe_out = FdNumpyPipe("pipe_out",fd_r,layout=LAYOUT)
    test_data = helpers.create_data(LAYOUT,length=LENGTH)
    #print(test_data['data'][:,1])

    
    async def writer():
      for block in helpers.to_chunks(test_data,270):
        await npipe_in.write(block)
        await asyncio.sleep(0.01)
      
    async def reader():
      blk_size = 357
      data_cursor = 0 #index into test_data
      run_count = 0 
      while(data_cursor!=len(test_data)):
        #consume all data in pipe
        data = await npipe_out.read()
        rows_used = min(len(data),blk_size)
        used_data = data[:rows_used]
        #print(used_data['data'][:,1])
        npipe_out.consume(rows_used)
        np.testing.assert_array_equal(used_data,
                                      test_data[data_cursor:data_cursor+len(used_data)])
        data_cursor+=len(used_data)
        run_count+=1
        
      #make sure the reads are broken up (otherwise test is lame...)
      self.assertGreater(run_count,2)

    tasks = [asyncio.ensure_future(writer()),
             asyncio.ensure_future(reader())]
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.gather(*tasks))

    npipe_in.close()
    npipe_out.close()

  def test_reconstructs_fragmented_data(self):
    LAYOUT="int8_2"; LENGTH=1000
    (fd_r,fd_w) = os.pipe()

    #wrap the file descriptors in numpypipes
    npipe_out = FdNumpyPipe("pipe_out",fd_r,layout=LAYOUT)
    test_data = helpers.create_data(LAYOUT,length=LENGTH)

    async def writer():
      b_data = test_data.tobytes()
      f = open(fd_w,'wb',0)
      f.write(b_data[:395])
      await asyncio.sleep(0.05)
      f.write(b_data[395:713])
      await asyncio.sleep(0.05)
      f.write(b_data[713:])
      f.close()

    async def reader():
      data_cursor = 0 #index into test_data
      run_count = 0 
      while(data_cursor!=len(test_data)):
        #consume all data in pipe
        data = await npipe_out.read()
        np.testing.assert_array_equal(data,
                                      test_data[data_cursor:data_cursor+len(data)])
        data_cursor+=len(data)
        run_count+=1
        
      #make sure the reads are broken up (otherwise test is lame...)
      self.assertGreater(run_count,2)
    
    tasks = [asyncio.ensure_future(writer()),
             asyncio.ensure_future(reader())]
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.gather(*tasks))
    npipe_out.close()

