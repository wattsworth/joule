import sys
import tempfile

from joule.client.helpers.args import module_args, validate_time_bounds, read_module_config
from joule.errors import ConfigurationError
from tests.helpers import AsyncTestCase


class TestNilmdbStore(AsyncTestCase):

    def test_module_args(self):
        # if the module config is not specified, return args
        # ignore the -h help flag, the main argparse should catch it
        sys.argv = ['exec_cmd', 'arg1', 'arg2', '-h']
        arg_list = module_args()
        self.assertEqual(['arg1', 'arg2', '-h'], arg_list)
        # if the module config file is present in the args
        # parse it and add the included arguments
        with tempfile.NamedTemporaryFile() as f:
            f.write(str.encode(
                """
                [Main]
                name = test
                exec_cmd = runit.sh
                [Arguments]
                marg1 = test1
                marg2 = test2
                [Inputs]
                [Outputs]
                """))
            f.flush()
            sys.argv = ['exec_cmd', 'arg1', '--module_config', f.name]
            arg_list = module_args()
            self.assertEqual(['arg1', '--module_config', f.name,
                              '--marg1', 'test1',
                              '--marg2', 'test2'], arg_list)

    def test_validate_time_bounds(self):
        # parses time strings
        start, end = validate_time_bounds("1 hour ago", "now")
        self.assertLess(start, end)

        # handles timestamps
        start, end = validate_time_bounds("1534884541000000", None)
        self.assertIsNone(end)
        self.assertEqual(start, 1534884541000000)

        # raises error if start > end
        with self.assertRaises(ConfigurationError):
            validate_time_bounds("1 hour ago", "2 hours ago")

    def test_read_module_config(self):
        # read the module config file
        with tempfile.NamedTemporaryFile() as f:
            f.write(str.encode(
                """
                [Main]
                name = test
                exec_cmd = runit.sh
                [Arguments]
               
                [Inputs]
                input1 = /test/input1
                input2 = /test/input2
                
                [Outputs]
                output1 = /test/output1
                output2 = /test/output2
                """))
            f.flush()
            config = read_module_config(f.name)
            self.assertIn('Inputs', config)
            self.assertIn('Outputs', config)
        # raises configuration error if file does not exist
        with self.assertRaises(ConfigurationError):
            read_module_config("/bad/file")
        # raises configuration error on invalid config
        with self.assertRaises(ConfigurationError):
            with tempfile.NamedTemporaryFile() as f:
                f.write(str.encode(
                    """
                    invalid config
                    """))
                f.flush()
                read_module_config(f.name)



