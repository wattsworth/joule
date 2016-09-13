from joule.daemon.cmd import DaemonCmd
import unittest

class TestCmdLineArguments(unittest.TestCase):
    def setUp(self):
        self.cmd = DaemonCmd()
        
    @unittest.expectedFailure
    def test_default_config_file(self):
        args = self.parser.parse_args("")
        self.daemon.run(args)
        self.assertIn("main", self.daemon.configs)

    @unittest.expectedFailure
    def test_it_requires_a_config_file(self):
        args = self.parser.parse_args("--config NOTHING")
        self.daemon.run(args)
        #assert(raises error, missing config file)
