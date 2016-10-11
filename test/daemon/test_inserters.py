"""
Test the inserter and decimator objects
"""
import unittest
from joule.daemon import inserter
import nilmdb
from unittest import mock
import numpy as np

class TestInserters(unittest.TestCase):
  def setUp(self):
    pass
    
  @mock.patch("joule.daemon.daemon.nilmdb.client.numpyclient.NumpyClient",autospec=True)
  def test_inserts_continuous_data(self,mock_client):
    path = ("/test/path")
    my_inserter = inserter.NilmDbInserter(mock_client,path,decimate=False)
    mock_db_inserter = mock.Mock()
    my_inserter.inserter = mock_db_inserter
    length = 100
    blk_size = 10
    #generate random data
    data = self.create_data(length=length)
    #insert it by block
    for i in range(int(length/blk_size)):
      my_inserter.queue.put(data[i*blk_size:i*blk_size+blk_size])
    #send everything to the database
    my_inserter.process_data()
    #check what got inserted
    res = mock_db_inserter.insert.call_args[0][0]
    for i in range(len(data)):
      self.assertEqual(data[i][0],res[i][0])
      self.assertEqual(data[i][1],res[i][1])
      
  def test_finalizes_missing_sections(self):
    pass

  def decimates_continuous_data(self):
    pass

  def finalizes_decimations_on_missing_sections(self):
    pass

  def handles_corrupt_database_error(self):
    pass

  def create_data(self,
                  length=10,
                  streams=1,
                  step=1000,            #in us
                  start=1476152086000): #10 Oct 2016 10:15PM
    """Create a random block of NilmDB data [ts, stream]"""
    ts = np.arange(start,start+step*length,step,dtype=np.uint64)
    data = np.random.rand(length,streams)
    return np.hstack((ts[:,None],data))
                  

