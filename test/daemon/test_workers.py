
"""
Test the inserter and decimator objects
"""
import unittest
import joule.daemon.worker as worker
from joule.daemon.inputmodule import InputModule
from joule.daemon.utils import NumpyPipe
import queue
import time

from unittest import mock

class TestWorkers(unittest.TestCase):
  def setUp(self):
    self.loop = asyncio.new_event_loop()
    asyncio.set_event_loop(None) #disable default event loop
"""
    mock_module = mock.create_autospec(InputModule)
    mock_module.is_alive = mock.Mock(return_value = False)
    mock_module.start = mock.Mock(return_value=mock.MagicMock())
    self.never_fails_module = mock_module
    mock_module = mock.create_autospec(InputModule)
    mock_module.is_alive = mock.Mock(return_value = False)
    mock_pipe = mock.MagicMock()
    mock_pipe.get = mock.Mock(side_effect=numpypipe.PipeEmpty)
    mock_module.start = mock.Mock(return_value=mock_pipe)
    self.always_fails_module = mock_module
"""

  @mock.patch("joule.daemon.worker.procdb_client",autospec=True)
  def test_passes_data_to_subscribers(self,mock_client):
    mock_module = mock.MagicMock()
    my_worker = worker.Worker(mock_module,module_timeout=0.1)
    num_queues = 4
    queues=[]
    for i in range(num_queues):
      queues.append(my_worker.subscribe(loop=self.loop))

    my_worker.run()
    mock_module.inject_data("data")
    time.sleep(0.2)
    my_worker.stop()
    my_worker.join()
    for q in output_queues:
      self.assertTrue(q.put.called)

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

