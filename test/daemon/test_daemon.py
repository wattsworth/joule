from joule.daemon.daemon import Daemon
import tempfile
import unittest
import os
from unittest import mock
import asyncio
from joule.utils import config_manager

class TestDaemonRun(unittest.TestCase):

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

  @mock.patch("joule.daemon.daemon.asyncio",autospec=True)
  def test_runs_modules_as_workers(self,mock_asyncio):
    daemon = Daemon()
    daemon._start_worker = mock.Mock()
    num_modules = 4
    daemon.input_modules = [mock.Mock() for x in range(num_modules)]
    loop = asyncio.new_event_loop()
    loop.run_until_complete(daemon.run(loop=loop))
    loop.close()
    self.assertEqual(mock_asyncio.ensure_future.call_count,num_modules)
    
