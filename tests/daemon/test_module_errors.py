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
               [Source]
                 path1 = /input/path1
               [Destination]
                 path1 = /output/path1

            """)

    def test_errors_on_missing_dest_section(self):
        self.base_config.remove_section("Destination")
        with self.assertRaises(DaemonError):
            self.parser.run(self.base_config)

    def test_errors_on_missing_main_section(self):
        self.base_config.remove_section("Main")
        with self.assertRaisesRegex(DaemonError, "Main"):
            self.parser.run(self.base_config)

    def test_errors_on_missing_name(self):
        self.base_config.remove_section("Main")
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

    def test_errors_on_invalid_source_streams_format(self):
        bad_input_streams = "/path/to/stream1,adfasdf,adf"
        self.base_config['Source']['streams'] = bad_input_streams
        with self.assertRaisesRegex(DaemonError, 'adfasdf'):
            self.parser.run(self.base_config)

    def test_errors_on_invalid_destination_streams_format(self):
        bad_input_streams = "/path/to/stream1,adfasdf,adf"
        self.base_config['Destination']['streams'] = bad_input_streams
        with self.assertRaisesRegex(DaemonError, 'adfasdf'):
            self.parser.run(self.base_config)

    @unittest.skip("TODO")
    def test_errors_on_duplicate_destinations(self):
        pass

    @unittest.skip("TODO")
    def test_errors_on_duplicate_sources(self):
        pass

    @unittest.skip("TODO")
    def test_errors_on_same_path_in_source_and_destination(self):
        pass
