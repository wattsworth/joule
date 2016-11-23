import unittest
import tempfile
from joule.cmds import helpers

class TestHelpers(unittest.TestCase):

  def test_loads_configuration_from_file(self):#,mock_load_configs):
    with tempfile.NamedTemporaryFile() as fp:
      fp.write(str.encode("""[NilmDB]
                             URL=http://newurl
                          """))
      fp.flush()
      configs = helpers.parse_config_file(fp.name,verify=False)
      self.assertTrue(configs.nilmdb.url,"http://newurl")
            

  def test_loads_default_configuration(self):
      configs = helpers.parse_config_file(None,verify=False)
      #configs have default values
      self.assertTrue(configs.nilmdb.url,"http://localhost/nilmdb")
