"""
Test the inserter and decimator objects
"""
import unittest
import joule.daemon.worker as worker
from joule.daemon.inputmodule import InputModule
import queue
import time

from unittest import mock

class TestWorkers(unittest.TestCase):
  def setUp(self):

    mock_module = mock.create_autospec(InputModule)
    mock_proc = mock.Mock()
    mock_proc.is_alive = mock.Mock(return_value = True)
    mock_module.start = mock.Mock(return_value=mock_proc)
    self.never_fails_module = mock_module
    mock_module = mock.create_autospec(InputModule)
    mock_proc = mock.Mock()
    mock_proc.is_alive = mock.Mock(return_value = False)
    mock_module.start = mock.Mock(return_value=mock_proc)
    self.always_fails_module = mock_module
    
  @mock.patch("joule.daemon.worker.procdb_client",autospec=True)
  def test_passes_data_to_subscribers(self,mock_client):
    data = "data"
    mock_module = self.never_fails_module
    my_worker = worker.Worker(mock_module,module_timeout=0.1)
    num_queues = 4
    output_queues = [queue.Queue() for x in range(num_queues)]
    for q in output_queues:
      my_worker.subscribe(q)      

    my_worker.start()
    q_in = mock_module.start.call_args[0][0]
    q_in.put("data")
    time.sleep(0.2)
    my_worker.stop()
    my_worker.join()
    for q in output_queues:
      self.assertEqual(q.get(),data)
      self.assertTrue(q.empty())

  @mock.patch("joule.daemon.worker.procdb_client",autospec=True)
  def test_restarts_failed_module_process(self,mock_client):
    mock_module = self.always_fails_module
    my_worker = worker.Worker(mock_module,module_timeout=0.1)
    with self.assertLogs(level='ERROR'):
      my_worker.start()
      time.sleep(0.2)
      my_worker.stop()
      my_worker.join()
    self.assertGreater(mock_module.start.call_count,1)

  
