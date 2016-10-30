
import unittest
from joule.utils import config_manager
import tempfile

class TestConfigManager(unittest.TestCase):

  def test_default_configuration(self):
    """Uses default configuration unless other settings are specified"""
    my_configs = config_manager.load_configs(verify=False)
    self.assertIsInstance(my_configs,config_manager.Configs)
    
  def test_defaults_verify(self):
    #have to provide a valid module directory
    with tempfile.TemporaryDirectory() as tempdirname:
      config = """
        [Jouled]
          ModuleDirectory = {directory}
      """.format(directory = tempdirname)
      my_configs = config_manager.load_configs(config)
      self.assertIsInstance(my_configs,config_manager.Configs)
    
  def test_accepts_customized_settings(self):
    LOG_LINES = 334
    config = """
      [ProcDB]
        MaxLogLines = {log_lines}
     """.format(log_lines = LOG_LINES)
    my_configs = config_manager.load_configs(config,verify=False)
    self.assertTrue(my_configs.procdb.max_log_lines,LOG_LINES)

  def test_verifies_custom_settings(self):
    """Raises InvalidConfiguration if settings are invalid"""
    #have to provide a valid module directory
    with tempfile.TemporaryDirectory() as tempdirname:
      config = """
        [Jouled]
          ModuleDirectory = {directory}
        [NilmDB]
          InsertionPeriod = -1
      """.format(directory = tempdirname)
      with self.assertRaisesRegex(config_manager.InvalidConfiguration,"InsertionPeriod"):
        config_manager.load_configs(config)
  
  def test_it_errors_out_if_bad_configs(self):
    config = "this is corrupt"
    with self.assertRaises(config_manager.InvalidConfiguration):
      config_manager.load_configs(config,verify=False)



