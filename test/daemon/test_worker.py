"""
Test how worker handles pipes with subprocess
Worker should pass fd to child process and close them
cleanly on exit
"""
import asynctest
import asyncio
from unittest import mock
import joule.daemon.worker as worker
from test import helpers
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
    #mock up a stream with int32_4 data format so numpypipe builds correctly
    self.myprocdb.find_stream_by_path = mock.Mock(return_value =
                                                  helpers.build_stream(name="stub",
                                                                       datatype="int32",
                                                                       num_elements=4))
    #build data sources for module
    self.q_in1 = asyncio.Queue()
    mock_worker1=mock.create_autospec(spec = worker.Worker)
    mock_worker1.subscribe=mock.Mock(return_value=self.q_in1)
    self.q_in2 = asyncio.Queue()
    mock_worker2=mock.create_autospec(spec = worker.Worker)
    mock_worker2.subscribe=mock.Mock(return_value=self.q_in2)

    self.myworker = worker.Worker(self.my_module,self.myprocdb)
    self.myworker.register_inputs({
      '/data/path1': mock_worker1.subscribe,
      '/data/path2': mock_worker2.subscribe
    })

  def test_pipes_data_to_and_from_the_module_process(self):
    #subscribe module to sample output streams
    DATA1 = helpers.create_data(layout="int32_4",length=100)
    DATA2 = helpers.create_data(layout="int32_4",length=250)
    q_out1 = self.myworker.subscribe('/output/path1')
    q_out2 = self.myworker.subscribe('/output/path2')

    self.q_in1.put_nowait(DATA1)
    self.q_in2.put_nowait(DATA2)

    self.my_module.exec_cmd = "python "+MODULE_ECHO_DATA
    loop = asyncio.get_event_loop()
    loop.run_until_complete(self.myworker.run(restart=False))

    output1 = q_out1.get_nowait()
    output2 = q_out2.get_nowait()
    #make sure child echoed data correctly
    np.testing.assert_array_equal(output1,DATA1)
    np.testing.assert_array_equal(output2,DATA2)
    self.assertTrue(q_out1.empty())
    self.assertTrue(q_out2.empty())

  def test_stops_module_process_on_command(self):
    loop = asyncio.get_event_loop()

    async def stop_worker():
      await asyncio.sleep(0.1)
      with self.assertLogs(level="WARNING"):
        await self.myworker.stop(loop)

    self.myworker.SIGTERM_TIMEOUT = 0.1 #don't wait to kill it
    tasks = [ asyncio.ensure_future(stop_worker()),
              asyncio.ensure_future(self.myworker.run(restart=True)) ]
    self.my_module.exec_cmd = "python "+MODULE_RUN_FOREVER
    loop.run_until_complete(asyncio.gather(*tasks))


  #**NOTE: intended as a warpper around run_until_complete but
  #  it seems like asyncio closes pipes with garbage collection
  #  so the numpypipe does not actually have to close the file descriptor
  #  and in fact this causes an error (see joule/utils/numpypipe)
  def _verify_no_file_descriptor_leakage(self,func,args=[]):
    proc = psutil.Process()
    orig_fds = proc.num_fds()
    func(*args)
    self.assertEqual(proc.num_fds(),orig_fds)
    
