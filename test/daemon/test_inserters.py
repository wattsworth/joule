"""
Test the inserter and decimator objects
"""
import unittest
from joule.daemon import inserter
from unittest import mock
import numpy as np
import asyncio
import asynctest
from . import helpers

class TestNilmDbInserter(asynctest.TestCase):

  def setUp(self):
    self.my_stream = helpers.build_stream(name="test",path="/test/path",num_elements=5)
    
  @mock.patch("joule.daemon.daemon.nilmdb.client.numpyclient.NumpyClient",autospec=True)
  @mock.patch("joule.daemon.inserter.NilmDbDecimator",autospec=True)
  def test_processes_data_from_queue(self,mock_decimator,mock_client):

    my_inserter = inserter.NilmDbInserter(mock_client,"/test/path",decimate=True)
    my_decimator= mock_decimator.return_value

    #generate random data
    length = 100
    interval_start = 500
    step = 100
    interval_end = interval_start+(length-1)*step
    data = helpers.create_data(self.my_stream,length=length,start=interval_start,step=step)
    
    #insert it by block
    blk_size = 10
    queue = asyncio.Queue(loop=self.loop)
    for i in range(int(length/blk_size)):
      queue.put_nowait(data[i*blk_size:i*blk_size+blk_size])
    #send everything to the database
    async def stop_inserter():
      await asyncio.sleep(0.01)
      my_inserter.stop()
    loop = asyncio.get_event_loop()
    tasks = [ asyncio.ensure_future(stop_inserter()),
              asyncio.ensure_future(my_inserter.process(queue,loop=loop)) ]
    loop.run_until_complete(asyncio.gather(*tasks))

    
    #check what got inserted
    call = mock_client.stream_insert_numpy.call_args
    _,inserted_data = call[0]
    start,end = (call[1]['start'],call[1]['end'])
    np.testing.assert_array_equal(inserted_data,data)
    self.assertEqual(start,interval_start)
    self.assertEqual(end,interval_end+1)

    #make sure the decimations were processed
    self.assertTrue(my_decimator.process.called)
    
  @mock.patch("joule.daemon.daemon.nilmdb.client.numpyclient.NumpyClient",autospec=True)      
  def test_detects_interval_breaks(self,mock_client):
    my_inserter = inserter.NilmDbInserter(mock_client,"/test/path",decimate=False)
    mock_db_inserter = mock.Mock()
    my_inserter.inserter = mock_db_inserter

    #missing data between two inserts
    interval1_start = 500; interval2_start = 1000;
    queue = asyncio.Queue(loop=self.loop)
    queue.put_nowait(helpers.create_data(self.my_stream,start=interval1_start,step=1))
    queue.put_nowait(None) #break in the data
    queue.put_nowait(helpers.create_data(self.my_stream,start=interval2_start,step=1))
                          
    #send everything to the database
    async def stop_inserter():
      await asyncio.sleep(0.01)
      my_inserter.stop()

    loop = asyncio.get_event_loop()
    tasks = [ asyncio.ensure_future(stop_inserter()),
              asyncio.ensure_future(my_inserter.process(queue,loop=loop)) ]


    loop.run_until_complete(asyncio.gather(*tasks))

    #make sure two seperate intervals made it to the database
    interval1 = mock_client.stream_insert_numpy.call_args_list[0]
    start = interval1[1]['start']
    self.assertEqual(start,interval1_start)
    interval2 = mock_client.stream_insert_numpy.call_args_list[1]
    start = interval2[1]['start']
    self.assertEqual(start,interval2_start)

class TestNilmDbDecimator(unittest.TestCase):
  
  def setUp(self):
    self.test_path = "/test/path"
    self.base_info = [self.test_path,"int8_4"]
    self.decim_lvl1_info = [self.test_path+"~decim-4","float32_12"]
    self.decim_lvl2_info = [self.test_path+"~decim-16","float32_12"]

  @mock.patch("joule.daemon.daemon.nilmdb.client.numpyclient.NumpyClient",autospec=True)      
  def test_finds_existing_streams(self,mock_client):
    #both the base and the decimation stream already exist
    mock_info = self.mock_stream_info([self.base_info,
                                       self.decim_lvl1_info])
    mock_client.stream_list = mock.Mock(side_effect=mock_info)
    inserter.NilmDbDecimator(mock_client,self.test_path)
    #so the decimation stream shouldn't be created
    mock_client.stream_create.assert_not_called()

  @mock.patch("joule.daemon.daemon.nilmdb.client.numpyclient.NumpyClient",autospec=True)      
  def test_creates_first_decimation_stream(self,mock_client):
    #only the base exists
    mock_info = self.mock_stream_info([self.base_info])
    mock_client.stream_list = mock.Mock(side_effect=mock_info)
    inserter.NilmDbDecimator(mock_client,self.test_path)
    #so the decimation stream should be created
    mock_client.stream_create.assert_called_with(*self.decim_lvl1_info)


  @mock.patch("joule.daemon.daemon.nilmdb.client.numpyclient.NumpyClient",autospec=True)      
  def test_creates_subsequent_decimation_streams(self,mock_client):
    #both the base and the decimation stream already exist
    mock_info = self.mock_stream_info([self.base_info,
                                       self.decim_lvl1_info])
    mock_client.stream_list = mock.Mock(side_effect=mock_info)
    inserter.NilmDbDecimator(mock_client,self.decim_lvl1_info[0])
    #the 2nd level decimation should be created
    mock_client.stream_create.assert_called_with(*self.decim_lvl2_info)

  @mock.patch("joule.daemon.daemon.nilmdb.client.numpyclient.NumpyClient",autospec=True)      
  def test_correctly_decimates_data(self,mock_client):
    #    vals = np.arange(1,17); ts = np.arange(1,17)*100 #some test data to decimate
    #    data = np.hstack((ts[:,None],vals[:,None]))
    my_stream = helpers.build_stream("test",path="/test/path",num_elements=1)
    data = helpers.create_data(my_stream,length=16)
    ts = data[:,0]; vals = data[:,1:];
    
    mock_info = self.mock_stream_info([self.base_info,
                                       self.decim_lvl1_info,
                                       self.decim_lvl2_info])
    mock_client.stream_list = mock.Mock(side_effect=mock_info)
    my_decimator = inserter.NilmDbDecimator(mock_client,self.base_info[0])
    my_decimator.process(data[:7]) #insert data in chunks to test decimation buffer
    my_decimator.process(data[7:])
    inserted_lvl2 = False 
    for args in mock_client.stream_insert_numpy.call_args_list:
      (path,data) = args[0]
      kwargs = args[1]
      if(path==self.decim_lvl2_info[0]):
        #upper decimations match incoming data bounds **note actual bounds here**
        #   the start/end match the data points *given* to this decimation level
        #   here we are looking at x16 so the timestamps are from the x4 stream
        #   so start is the mean of the first 4  timestamps, and end is likewise
        self.assertEqual(kwargs['start'],np.mean(ts[:4]))
        self.assertEqual(kwargs['end'],np.mean(ts[-4:]))
        #check the contents of the data array
        np.testing.assert_array_almost_equal(data,[[np.mean(ts),   #average ts
                                             np.mean(vals), # data mean,min,ma
                                             np.min(vals),
                                             np.max(vals)]])
        inserted_lvl2=True
    self.assertTrue(inserted_lvl2) #make sure level2 (x16) decimation was performed

  def test_finalize_inserts_interval_break(self):
    pass


  def mock_stream_info(self,streams):
    """pass in array of stream_info's:
       [['/test/path','float32_3'],
       ['/test/path2','float32_5'],...]
       returns a function to mock stream_info as a side_effect"""
    
    def stream_info(path):
      for stream in streams:
        if(stream[0]==path):
          return [stream]
      return []
    return stream_info
