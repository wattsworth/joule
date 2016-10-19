
import unittest
from joule.utils.numpypipe import NumpyPipe
import os
import numpy as np
from unittest import mock

class TestNumpyPipe(unittest.TestCase):
  def setUp(self):
    pass

  def test_passes_numpy_data(self):
    (rpipe,wpipe) = os.pipe()
    np_pipe = NumpyPipe(rpipe,num_streams=1)
    
    data = self._create_data()
    b_data = data.tobytes()
    with os.fdopen(wpipe,'wb') as w:
      with np_pipe.open():
        w.write(b_data[:100])
        w.flush()
        x1 = np_pipe.get()
        w.write(b_data[100:])
        w.flush()
        x2 = np_pipe.get()
        
    np.testing.assert_array_equal(np.vstack((x1,x2)),data)
    w.close()
    
  def _create_data(timestamped=True,
                     length=100,
                     streams=1):
    start=1476152086000 #10 Oct 2016 10:15PM
    step = 1000
    """Create a random block of NilmDB data [ts, stream]"""
    ts = np.arange(start,start+step*length,step,dtype=np.uint64)
    data = np.random.rand(length,streams)
    return np.hstack((ts[:,None],data))
