"""
Test how worker handles pipes with subprocess
Worker should pass fd to child process and close them
cleanly on exit
"""
import asynctest
import asyncio
from unittest import mock
import joule.daemon.worker as worker
from . import helpers
from joule.procdb.client import SQLClient
import os
import psutil
import numpy as np

MODULE_ECHO_DATA = os.path.join(os.path.dirname(__file__), 'worker_scripts','echo_data.py')
MODULE_RUN_FOREVER = os.path.join(os.path.dirname(__file__), 'worker_scripts','run_forever.py')

class TestWorker(asynctest.TestCase):
  def setUp(self):
    self.my_module = helpers.build_module(name="my_module",
                                          exec_cmd = "<<TODO>>",
                                          source_paths={
                                            'path1':'/data/path1',
                                            'path2':'/data/path2'},
                                          destination_paths={
                                            'path1':'/output/path1',
                                            'path2':'/output/path2'})

    self.myprocdb = mock.create_autospec(spec = SQLClient)
    #mock up a stream with float64_1 data format so numpypipe builds correctly
    self.myprocdb.find_stream_by_path = mock.Mock(return_value =
                                                  helpers.build_stream(name="stub",num_elements=1))
    #build data sources for module
    self.q_in1 = asyncio.Queue()
    mock_worker1=mock.create_autospec(spec = worker.Worker)
    mock_worker1.subscribe=mock.Mock(return_value=self.q_in1)
    self.q_in2 = asyncio.Queue()
    mock_worker2=mock.create_autospec(spec = worker.Worker)
    mock_worker2.subscribe=mock.Mock(return_value=self.q_in2)

    self.myworker = worker.Worker(self.my_module,self.myprocdb)
    self.myworker.register_inputs({
      '/data/path1': mock_worker1,
      '/data/path2': mock_worker2
    })

  def test_pipes_data_to_and_from_the_module_process(self):
    #subscribe module to sample output streams
    DATA1 = np.array([[1.0,2.0],[3.0,4.0]])
    DATA2 = np.array([[5.0,6.0],[7.0,8.0]])
    q1_out = self.myworker.subscribe('/output/path1')
    q2_out = self.myworker.subscribe('/output/path2')
    loop = asyncio.get_event_loop()
    self.q_in1.put_nowait(DATA1)
    self.q_in2.put_nowait(DATA2)

    self.my_module.exec_cmd = "python "+MODULE_ECHO_DATA
    self._verify_no_file_descriptor_leakage(
      loop.run_until_complete, args = [(self.myworker.run(restart=False))])

    q1_output = q1_out.get_nowait()
    q2_output = q2_out.get_nowait()
    #make sure child echoed data correctly
    np.testing.assert_array_equal(q1_output,DATA1)
    np.testing.assert_array_equal(q2_output,DATA2)
    self.assertTrue(q1_out.empty())
    self.assertTrue(q2_out.empty())


    loop.close()

  def test_stops_module_process_on_command(self):
    loop = asyncio.get_event_loop()

    async def stop_worker():
      await asyncio.sleep(0.5)
      with self.assertLogs(level="WARNING"):
        await self.myworker.stop(loop)
      
    tasks = [ asyncio.ensure_future(stop_worker()),
              asyncio.ensure_future(self.myworker.run(restart=True)) ]
    self.my_module.exec_cmd = "python "+MODULE_RUN_FOREVER
    self._verify_no_file_descriptor_leakage(
      loop.run_until_complete, args = [asyncio.gather(*tasks)])


  def _verify_no_file_descriptor_leakage(self,func,args=[]):
    proc = psutil.Process()
    orig_fds = proc.num_fds()
    func(*args)
    self.assertEqual(proc.num_fds(),orig_fds)
    
