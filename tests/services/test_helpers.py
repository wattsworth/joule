import unittest
import tempfile
import os
import stat

from joule.services.helpers import load_configs


class TestHelpers(unittest.TestCase):

    def test_parses_conf_files_in_path(self):
        """parses files ending in *.conf and ignores others"""
        file_names = ['stream1.conf', 'ignored',
                      'temp.conf~', 'streamA-3.conf']

        with tempfile.TemporaryDirectory() as conf_dir:
            for name in file_names:
                # create a stub stream configuration (needed for
                # configparser)
                with open(os.path.join(conf_dir, name), 'w') as f:
                    f.write('[Main]\n')

            configs = load_configs(conf_dir)
        self.assertEqual(2, len(configs))
        self.assertTrue('stream1.conf' in configs.keys())
        self.assertTrue('streamA-3.conf' in configs.keys())

    def test_logs_invalid_files(self):
        """parses files ending in *.conf and ignores others"""

        with tempfile.TemporaryDirectory() as conf_dir:
            with open(os.path.join(conf_dir, 'setting.conf'), 'w') as f:
                f.write('invalid\n')
            with open(os.path.join(conf_dir, 'noread.conf'), 'w') as f:
                f.write('[Main]\n')
            os.chmod(os.path.join(conf_dir, 'noread.conf'), stat.S_IWUSR)
            with self.assertLogs(level="ERROR"):
                configs = load_configs(conf_dir)
                self.assertEqual(len(configs), 0)