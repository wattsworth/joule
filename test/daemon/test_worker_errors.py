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
import re

MODULE_FAILS_ON_ERROR = os.path.join(os.path.dirname(__file__), 'worker_scripts','fails_on_error.py')


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

  def test_exits_cleanly_on_module_error(self):
    proc = psutil.Process()
    self.my_module.exec_cmd = "causes error"
    loop = asyncio.get_event_loop()
    orig_fds = proc.num_fds()
    with self.assertLogs(level='ERROR'):
      loop.run_until_complete(self.myworker.run(restart=False))
    self.assertEqual(proc.num_fds(),orig_fds)    
    loop.close()

  @asynctest.fail_on(unused_loop = False)
  def test_does_not_register_if_missing_paths(self):
    status = self.myworker.register_inputs({
      '/data/path1': mock.create_autospec(spec = worker.Worker)
    })
    self.assertFalse(status)
      

  def test_all_inputs_must_be_registered(self):
    loop = asyncio.get_event_loop()
    self.my_module.source_paths['missing'] = '/unregistered/input'
    self.myworker = worker.Worker(self.my_module,self.myprocdb)

    with self.assertLogs(level='ERROR'):
      self._verify_no_file_descriptor_leakage(
        loop.run_until_complete, args = [self.myworker.run(restart=False)])
      

  def test_restarts_failed_module_process(self):
    loop = asyncio.get_event_loop()
    
    async def stop_worker():
      await asyncio.sleep(0.5)
      await self.myworker.stop(loop)

    tasks = [ asyncio.ensure_future(stop_worker()),
              asyncio.ensure_future(self.myworker.run(restart=True)) ]
    self.my_module.exec_cmd = "python "+ MODULE_FAILS_ON_ERROR
    q1 = self.myworker.subscribe("/output/path1")
    q2 = self.myworker.subscribe("/output/path2")
    with self.assertLogs(level="ERROR") as cm:
      self._verify_no_file_descriptor_leakage(
        loop.run_until_complete, args = [asyncio.gather(*tasks)])
    #make sure there are empty arrays in the output queues for every restart
    num_restarts = 0
    for entry in cm.output:
      if(bool(re.search("Restart",entry))):
        num_restarts += 1
        self.assertEqual(None,q1.get_nowait())
        self.assertEqual(None,q2.get_nowait())
    #make sure there were at least two restarts
    self.assertGreater(num_restarts,1)
    #..and nothing else should be in the queues
    self.assertTrue(q1.empty())
    self.assertTrue(q2.empty())

  def _verify_no_file_descriptor_leakage(self,func,args=[]):
    proc = psutil.Process()
    orig_fds = proc.num_fds()
    func(*args)
    self.assertEqual(proc.num_fds(),orig_fds)
    

  
