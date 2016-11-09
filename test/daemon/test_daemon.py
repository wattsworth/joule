from joule.daemon.daemon import Daemon
from joule.daemon import daemon
import tempfile
import unittest
import os
from unittest import mock
import asyncio
import asynctest
from joule.utils import config_manager

class TestDaemonSetup(unittest.TestCase):
  @mock.patch("joule.daemon.daemon.InputModule",autospec=True)
  @mock.patch("joule.daemon.daemon.procdb_client",autospec=True)
  def test_it_creates_modules(self,mock_procdb,mock_module):
    """creates a module for every *.conf file and ignores others"""
    module_names = ['module1.conf','ignored','temp.conf~','module2.conf']
    MODULE_COUNT = 2
    with tempfile.TemporaryDirectory() as dir:
        for name in module_names:
            #create a stub module configuration (needed for configparser)
            with open(os.path.join(dir,name),'w') as f:
                f.write('[Main]\n')
        custom_config = """
         [Jouled]
           ModuleDirectory={dir}
        """.format(dir=dir)
        configs = config_manager.load_configs(custom_config,verify=False)
        daemon = Daemon()
        daemon.initialize(configs)
        self.assertEqual(MODULE_COUNT,len(daemon.input_modules))

  @mock.patch("joule.daemon.daemon.config_manager",autospec=True)
  def test_daemon_reads_config_file(self,mock_configs):
    CUSTOM_CONFIGURATION="custom_configuration"
    with tempfile.NamedTemporaryFile() as fp:
        fp.write(str.encode(CUSTOM_CONFIGURATION))
        fp.flush()
        daemon.load_configs(fp.name)
    mock_configs.load_configs.assert_called_with(config_string=CUSTOM_CONFIGURATION)

    
class TestDaemonRun(asynctest.TestCase):
  @asynctest.patch("joule.daemon.daemon.Worker",autospec=True)
  @asynctest.patch("joule.daemon.daemon.inserter.NilmDbInserter",autospec=True)
  def test_runs_modules_as_workers(self,mock_inserter,mock_worker):
    """daemon starts a worker and inserter for every module"""
    NUM_MODULES=4

    inserter_runs = 0
    async def run_inserter(*args):
      nonlocal inserter_runs
      inserter_runs += 1
    instance = mock_inserter.return_value
    instance.process = run_inserter

    worker_runs = 0
    async def run_worker():
      nonlocal worker_runs
      worker_runs += 1
    instance = mock_worker.return_value
    instance.run = run_worker
    instance.module = mock.Mock() #should be set by daemon but the object is mocked
    
    daemon = Daemon()
    daemon.procdb = mock.Mock()
    daemon.input_modules = [mock.Mock() for x in range(NUM_MODULES)]
    loop = asyncio.get_event_loop()
    daemon.stop_requested = True
    daemon.run(loop)
    
    self.assertEqual(inserter_runs,NUM_MODULES)
    self.assertEqual(worker_runs,NUM_MODULES)
    
