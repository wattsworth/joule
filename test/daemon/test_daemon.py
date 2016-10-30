from joule.daemon.daemon import Daemon
import tempfile
import unittest
import os
from unittest import mock
import threading
import time


class TestDaemonRun(unittest.TestCase):
  def setUp(self):
    pass

  @mock.patch("joule.daemon.daemon.InputModule",autospec=True)
  @mock.patch("joule.daemon.daemon.procdb_client",autospec=True)
  def test_it_creates_modules(self,mock_procdb,mock_module):
    """creates a module for every *.conf file (ignores others"""
    module_names = ['module1.conf','ignored','temp.conf~','module2.conf']
    MODULE_COUNT = 2
    with tempfile.TemporaryDirectory() as dir:
        for name in module_names:
            #create a stub module configuration (needed for configparser)
            with open(os.path.join(dir,name),'w') as f:
                f.write('[Main]\n')
        config = self.parse_configs("""
        [Main]
        """)
        config["Main"]["InputModuleDir"]= dir
        self.daemon.initialize(config)
        self.assertEqual(MODULE_COUNT,len(self.daemon.input_modules))

  def test_runs_modules_as_workers(self):
    daemon = Daemon()
    daemon.insertion_period = 0.1 #speed things up
    start_worker = mock.Mock()
    daemon._start_worker = start_worker
    num_modules = 4
    daemon.input_modules = [mock.Mock() for x in range(num_modules)]
    t = threading.Thread(target = daemon.run)
    t.start()
    time.sleep(0.1)
    daemon.stop()
    t.join()
    self.assertEqual(start_worker.call_count,num_modules)
    

