from joule.daemon.inputmodule import InputModule
import joule.daemon.inputmodule as inputmodule
from joule.daemon.errors import DaemonError
import test.util as util
import unittest

class TestConfigFile(unittest.TestCase):
    def setUp(self):
        self.module = InputModule()
        self.base_config = util.parse_configs(
            """[Main]
                 name = module name
                 description = optional
                 exec = /path/to/exec --args
               [Source]
                 path1 = /input/path1
               [Destination]
                 path = /simple/demo
                 datatype = float32
                 keep = 1w
               [Stream1]
                 name = stream1
            """)
    def test_parses_base_config(self):
        us_in_week = 7*24*60*60*1e6
        self.module.initialize(self.base_config)
        self.assertEqual(us_in_week,self.module.destination.keep_us)
    def test_errors_on_missing_dest_section(self):
        self.base_config.remove_section("Destination")
        with self.assertRaises(DaemonError):
            self.module.initialize(self.base_config)
    def test_errors_on_missing_main_section(self):
        self.base_config.remove_section("Main")
        with self.assertRaisesRegex(DaemonError,"Main"):
            self.module.initialize(self.base_config)
        
    def test_errors_on_missing_name(self):
        self.base_config.remove_section("Main")
        with self.assertRaises(DaemonError):
            self.module.initialize(self.base_config)        
    def test_errors_on_blank_name(self):
        self.base_config['Main']['name']=""
        with self.assertRaisesRegex(DaemonError,"name"):
            self.module.initialize(self.base_config)        
    def test_errors_on_missing_exec(self):
        self.base_config.remove_option('Main','exec')
        with self.assertRaisesRegex(DaemonError,"exec"):
            self.module.initialize(self.base_config)        
        
    def test_errors_on_missing_stream_sections(self):
        """Must have at least one stream"""
        self.base_config.remove_section("Stream1")
        with self.assertRaises(DaemonError):
            self.module.initialize(self.base_config)



    def test_sets_source_streams(self):
        input_paths = ["/path/to/stream1","/path/to/stream2","/path/to/stream3"]
        x = 1
        for path in input_paths:
            self.base_config['Source']['path%d'%x] = path
            x+=1
        self.module.initialize(self.base_config)
        self.assertListEqual(input_paths,self.module.source_paths)

    def test_rejects_invalid_formatting_on_source_streams(self):
        bad_input_streams = "/path/to/stream1,adfasdf,adf"
        self.base_config.remove_option('Source','exec')
        self.base_config['Source']['streams']=bad_input_streams
        with self.assertRaisesRegex(DaemonError,'adfasdf'):
            self.module.initialize(self.base_config)
        
        
    
