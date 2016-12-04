
import unittest
from joule.utils import config_manager
import tempfile
from test import helpers

class TestConfigManager(unittest.TestCase):

  def setUp(self):
    procdb_config = config_manager.ProcdbConfigs("/tmp/joule-proc-db.sqlite",
                                                 100)
    nilmdb_config = config_manager.NilmDbConfigs("http://localhost/nilmdb",
                                                 5)
    jouled_config = config_manager.JouledConfigs("/etc/joule/module_configs",
                                                 "/etc/joule/stream_configs")
    self.defaults = config_manager.Configs(procdb_config,
                                           jouled_config,
                                           nilmdb_config)
                                                 

  def test_loads_default_configuration(self):
    """Uses default configuration unless other settings are specified"""
    default_configs = config_manager.load_configs(verify=False)
    self.assertEqual(self.defaults,default_configs)

  def test_accepts_custom_settings(self):
    helpers.default_config['NilmDB']['InsertionPeriod']="10"
    helpers.default_config['ProcDB']['MaxLogLines']="13"
    helpers.default_config['Jouled']['ModuleDirectory']='/some/other/path'
    my_configs = config_manager.load_configs(helpers.default_config,verify=False)
    self.assertEqual(my_configs.nilmdb.insertion_period,10)
    self.assertEqual(my_configs.procdb.max_log_lines,13)
    self.assertEqual(my_configs.jouled.module_directory,'/some/other/path')
    
  def test_defaults_verify(self):
    #have to provide valid directories
    with tempfile.TemporaryDirectory() as temp:
      helpers.default_config['Jouled']['ModuleDirectory']=temp
      helpers.default_config['Jouled']['StreamDirectory']=temp
      my_configs = config_manager.load_configs(helpers.default_config)
      self.assertIsInstance(my_configs,config_manager.Configs)
    



