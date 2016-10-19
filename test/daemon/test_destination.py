import joule.daemon.destination as destination
import joule.daemon.stream as stream
from joule.daemon.errors import DaemonError
import test.util as util
import unittest

class TestConfigFile(unittest.TestCase):
    def setUp(self):
        self.parser = destination.Parser()
        config = util.parse_configs(
            """[Destination]
                 path = /simple/demo
                 datatype = float32
                 keep = 1w
            """)
        self.base_config = config['Destination']
    def test_parses_base_config(self):
        us_in_week = 7*24*60*60*1e6
        destination = self.parser.run(self.base_config)
        self.assertEqual(destination.keep_us,us_in_week)
    def test_errors_on_bad_path(self):
        """path must be of form /dir/subdir/../file"""
        bad_paths=["","bad name","/tooshort","/*bad&symb()ls"]
        self.evaluate_bad_values("path",bad_paths)
    def test_errors_on_bad_keep(self):
        """keep is # and timeunit (eg 1w, 30h, 2y) or False"""
        bad_keeps=["0w","3","w","something random","-2h"]
        self.evaluate_bad_values("keep",bad_keeps)
    def test_errors_on_bad_datatype(self):
        bad_datatypes=["","intz","0"]
        self.evaluate_bad_values("datatype",bad_datatypes)
    def test_computes_data_format(self):
        """data_format returns float32_4 for example"""
        dest = util.stub_destination(datatype="float32")
        for i in range(4):
            dest.add_stream(stream.build_stream(name="%d"%i))
        self.assertEqual(dest.data_format,"float32_4")
    def test_allows_no_keep(self):
        config = util.parse_configs(
            """[Destination]
                 path = /simple/demo
                 datatype = float32
                 keep = None
            """)
        destination = self.parser.run(config['Destination'])
        self.assertEqual(destination.keep_us,0)
        

    def evaluate_bad_values(self,setting_name,bad_settings):
        for setting in bad_settings:
            with self.subTest(setting=setting):
                self.base_config[setting_name]=setting
                with self.assertRaisesRegex(DaemonError,setting_name):
                    self.parser.run(self.base_config)

        
