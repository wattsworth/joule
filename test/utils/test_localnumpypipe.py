import asynctest
from . import helpers
import numpy as np
import asyncio

from joule.utils.localnumpypipe import LocalNumpyPipe

class TestLocalNumpyPipe(asynctest.TestCase):

  def test_pipes_numpy_arrays(self):
    LAYOUT="int8_2"; LENGTH=100
    my_pipe = LocalNumpyPipe(name="my_pipe",layout=LAYOUT)
    subscriber_pipe = LocalNumpyPipe(name="subscriber",layout=LAYOUT)
    my_pipe.subscribe(subscriber_pipe)
    test_data = helpers.create_data(LAYOUT,length=LENGTH)
#    print(test_data['data'][:,1])
    async def writer():
      NUM_WRITE_BLOCKS = 3
      for i in range(NUM_WRITE_BLOCKS):
        blk_size = int(np.ceil(len(test_data)/NUM_WRITE_BLOCKS))
        blk_start = i*blk_size
        blk_end = min((i+1)*blk_size,len(test_data))
        await my_pipe.write(test_data[blk_start:blk_end])


    async def reader():
      NUM_READ_BLOCKS=7
      blk_size = int(np.ceil(len(test_data)/NUM_READ_BLOCKS))
      data_cursor = 0 #index into test_data
      while(data_cursor!=len(test_data)):
        #consume all data in pipe (might be more than NUM_READ_BLOCKS)
        data = await my_pipe.read()
        rows_used = min(len(data),blk_size)
        used_data = data[:rows_used]
        #print(used_data['data'][:,1])
        my_pipe.consume(rows_used)
        np.testing.assert_array_equal(used_data,
                                      test_data[data_cursor:data_cursor+len(used_data)])
        data_cursor+=len(used_data)

    async def subscriber():
      NUM_READ_BLOCKS=17
      blk_size = int(np.ceil(len(test_data)/NUM_READ_BLOCKS))
      data_cursor = 0 #index into test_data
      while(data_cursor!=len(test_data)):
        #consume all data in pipe (might be more than NUM_READ_BLOCKS)
        data = await subscriber_pipe.read()
        rows_used = min(len(data),blk_size)
        used_data = data[:rows_used]
        #print(used_data['data'][:,1])
        subscriber_pipe.consume(rows_used)
        np.testing.assert_array_equal(used_data,
                                      test_data[data_cursor:data_cursor+len(used_data)])
        data_cursor+=len(used_data)

    loop = asyncio.get_event_loop()
    tasks = [asyncio.ensure_future(writer()),
             asyncio.ensure_future(reader()),
             asyncio.ensure_future(subscriber())]
    
    loop.run_until_complete(asyncio.gather(*tasks))

  
