import unittest
import sys
import tempfile

from joule import utilities
from joule.client.helpers.args import module_args


class TestNilmdbStore(unittest.TestCase):

    def test_yesno(self):
        self.assertTrue(utilities.yesno("yes"))
        self.assertFalse(utilities.yesno("no"))
        for val in ["badval", "", None]:
            with self.assertRaises(ValueError):
                utilities.yesno(val)

    def test_module_args(self):
        # if the module config is not specified, return args
        # ignore the -h help flag, the main argparse should catch it
        sys.argv = ['exec_cmd','arg1','arg2', '-h']
        arg_list = module_args()
        self.assertEqual(['arg1','arg2', '-h'], arg_list)
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
                              '--marg1','test1',
                              '--marg2','test2'], arg_list)


