"""
Test the inserter and decimator objects
"""
import unittest
from joule.daemon import inserter
from unittest import mock
import numpy as np
import asyncio

class TestNilmDbInserter(unittest.TestCase):
  def setUp(self):
    self.loop = asyncio.new_event_loop()
    asyncio.set_event_loop(None) #disable default event loop

  def tearDown(self):
    self.loop.close()
    
  @mock.patch("joule.daemon.daemon.nilmdb.client.numpyclient.NumpyClient",autospec=True)
  def test_inserts_continuous_data(self,mock_client):
    my_inserter = inserter.NilmDbInserter(mock_client,"/test/path",decimate=False)

    #generate random data
    length = 100
    interval_start = 500
    step = 100
    interval_end = interval_start+(length-1)*step
    data = self.create_data(length=length,start=interval_start,step=step)
    
    #insert it by block
    blk_size = 10
    queue = asyncio.Queue(loop=self.loop)
    for i in range(int(length/blk_size)):
      queue.put_nowait(data[i*blk_size:i*blk_size+blk_size])
    #send everything to the database
    self.loop.run_until_complete(my_inserter.process(queue,run_once=True,loop=self.loop))

    
    #check what got inserted
    call = mock_client.stream_insert_numpy.call_args
    _,inserted_data = call[0]
    start,end = (call[1]['start'],call[1]['end'])
    np.testing.assert_array_equal(inserted_data,data)
    self.assertEqual(start,interval_start)
    self.assertEqual(end,interval_end+1)

  @mock.patch("joule.daemon.daemon.nilmdb.client.numpyclient.NumpyClient",autospec=True)      
  def test_finalizes_missing_sections(self,mock_client):
    my_inserter = inserter.NilmDbInserter(mock_client,"/test/path",decimate=False)
    mock_db_inserter = mock.Mock()
    my_inserter.inserter = mock_db_inserter

    #missing data between two inserts
    interval1_start = 500; interval2_start = 1000;
    queue = asyncio.Queue(loop=self.loop)
    queue.put_nowait(self.create_data(start=interval1_start,step=1))
    queue.put_nowait(None)
    queue.put_nowait(self.create_data(start=interval2_start,step=1))
                          

    #send everything to the database
    self.loop.run_until_complete(my_inserter.process(queue,run_once=True,loop=self.loop))

    #make sure two seperate intervals made it to the database
    interval1 = mock_client.stream_insert_numpy.call_args_list[0]
    start = interval1[1]['start']
    self.assertEqual(start,interval1_start)
    interval2 = mock_client.stream_insert_numpy.call_args_list[1]
    start = interval2[1]['start']
    self.assertEqual(start,interval2_start)
  
  def create_data(self,
                  length=10,
                  streams=1,
                  step=1000,            #in us
                  start=1476152086000): #10 Oct 2016 10:15PM
    """Create a random block of NilmDB data [ts, stream]"""
    ts = np.arange(start,start+step*length,step,dtype=np.uint64)
    data = np.random.rand(length,streams)
    return np.hstack((ts[:,None],data))
                  


    
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
    vals = np.arange(1,17); ts = np.arange(1,17)*100 #some test data to decimate
    data = np.hstack((ts[:,None],vals[:,None]))
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
        self.assertEqual(kwargs['start'],250) #upper decimations match incoming data bounds
        self.assertEqual(kwargs['end'],1450)  #
        #check the contents of the data array
        np.testing.assert_array_equal(data,[[np.mean(ts),   #average ts
                                             np.mean(vals), # data mean,min,ma
                                             np.min(vals),
                                             np.max(vals)]])
        inserted_lvl2=True
    self.assertTrue(inserted_lvl2) #make sure level2 (x16) decimation was performed

  @unittest.skip("TODO but code is written")
  def test_finalizes_decimations_on_missing_sections(self):
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
