"""
Test how worker handles pipes with subprocess
Worker should pass fd to child process and close them
cleanly on exit
"""
import asynctest
import asyncio
from unittest import mock
import joule.daemon.worker as worker
import joule.daemon.inputmodule as inputmodule
from joule.procdb.client import SQLClient
import os
import psutil
import numpy as np

MODULE_EXEC_FILENAME = os.path.join(os.path.dirname(__file__), 'worker_pipe_module_code.py')

class TestWorkerPipes(asynctest.TestCase):
  def setUp(self):
    self.mymodule = inputmodule.InputModule()
    self.mymodule.exec_cmd = "python %s"%MODULE_EXEC_FILENAME
    self.mymodule.numpy_columns = mock.Mock(return_value = 2)
    self.mymodule.source_paths = {
      'path1':'/data/path1',
      'path2':'/data/path2'
    }
    self.myprocdb = mock.create_autospec(spec = SQLClient)

    self.q_in1 = asyncio.Queue()
    mock_worker1=mock.create_autospec(spec = worker.Worker)
    mock_worker1.subscribe=mock.Mock(return_value=self.q_in1)
    self.q_in2 = asyncio.Queue()
    mock_worker2=mock.create_autospec(spec = worker.Worker)
    mock_worker2.subscribe=mock.Mock(return_value=self.q_in2)

    self.myworker = worker.Worker(self.mymodule,self.myprocdb)
    self.myworker.register_inputs({
      '/data/path1': mock_worker1,
      '/data/path2': mock_worker2
    })

  def test_exits_cleanly_on_error(self):
    proc = psutil.Process()
    self.mymodule.exec_cmd = "causes error"
    loop = asyncio.get_event_loop()
    orig_fds = proc.num_fds()
    with self.assertLogs(level='ERROR'):
      loop.run_until_complete(self.myworker.run(restart=False))
    self.assertEqual(proc.num_fds(),orig_fds)    
    loop.close()

  def test_handles_multiple_source_pipes(self):
    q_out = self.myworker.subscribe()
    loop = asyncio.get_event_loop()
    mock_data1=mock.Mock()
    mock_data1.tobytes=mock.Mock(return_value=b'test1')
    self.q_in1.put_nowait(mock_data1)
    mock_data2 = mock.Mock()
    mock_data2.tobytes=mock.Mock(return_value=b'test2')
    self.q_in2.put_nowait(mock_data2)
    proc = psutil.Process()
    orig_fds = proc.num_fds()
    loop.run_until_complete(self.myworker.run(restart=False))
    actual_output = q_out.get_nowait()
    expected_output = np.array([[1.0,2.0],[3.0,4.0]])
    #make sure child ran correctly
    np.testing.assert_array_equal(actual_output,expected_output)
    self.assertTrue(q_out.empty())
    #make sure all fd's are closed
    self.assertEqual(proc.num_fds(),orig_fds)
    loop.close()
