from joule.daemon import module
from joule.daemon.errors import DaemonError
from tests import helpers
import unittest


class TestModule(unittest.TestCase):

    def setUp(self):
        self.parser = module.Parser()
        self.base_config = helpers.parse_configs(
            """[Main]
                 name = module name
                 description = optional
                 exec = /path/to/exec --args
               [Arguments]
                 arg1 = 4
                 arg2 = a multiline
                   argument that goes on
                   and on
               [Inputs]
                 path1 = /input/path1
               [Outputs]
                 path1 = /output/path1

            """)

    def test_errors_on_missing_dest_section(self):
        self.base_config.remove_section("Output")
        with self.assertRaises(DaemonError):
            self.parser.run(self.base_config)

    def test_errors_on_missing_main_section(self):
        self.base_config.remove_section("Main")
        with self.assertRaisesRegex(DaemonError, "Main"):
            self.parser.run(self.base_config)

    def test_errors_on_missing_name(self):
        del self.base_config['Main']['name']
        with self.assertRaises(DaemonError):
            self.parser.run(self.base_config)

    def test_errors_on_blank_name(self):
        self.base_config['Main']['name'] = ""
        with self.assertRaisesRegex(DaemonError, "name"):
            self.parser.run(self.base_config)

    def test_errors_on_missing_exec(self):
        self.base_config.remove_option('Main', 'exec')
        with self.assertRaisesRegex(DaemonError, "exec"):
            self.parser.run(self.base_config)

    def test_errors_on_blank_exec(self):
        self.base_config['Main']['exec_cmd'] = ""
        with self.assertRaisesRegex(DaemonError, "exec_cmd"):
            self.parser.run(self.base_config)

    def test_errors_on_invalid_input_streams_format(self):
        bad_input_streams = "/path/to/stream1,adfasdf,adf"
        self.base_config['Inputs']['streams'] = bad_input_streams
        with self.assertRaisesRegex(DaemonError, 'adfasdf'):
            self.parser.run(self.base_config)

    def test_errors_on_invalid_output_streams_format(self):
        bad_input_streams = "/path/to/stream1,adfasdf,adf"
        self.base_config['Outputs']['streams'] = bad_input_streams
        with self.assertRaisesRegex(DaemonError, 'adfasdf'):
            self.parser.run(self.base_config)

    @unittest.skip("TODO")
    def test_errors_on_duplicate_outputs(self):
        pass

    @unittest.skip("TODO")
    def test_errors_on_duplicate_inputs(self):
        pass

    @unittest.skip("TODO")
    def test_errors_on_same_path_in_input_and_output(self):
        pass
