
import unittest
import os
import tempfile

from joule.models import config
from tests import helpers


class TestConfigManagerErrors(unittest.TestCase):

    def test_errors_on_invalid_directories(self):
        with tempfile.TemporaryDirectory() as temp:
            helpers.default_config['Jouled']['ModuleDirectory'] = temp
            helpers.default_config['Jouled'][
                'StreamDirectory'] = "/invalid/path"
            with self.assertRaisesRegex(config.InvalidConfiguration, "StreamDirectory"):
                config.load_configs(helpers.default_config)

            helpers.default_config['Jouled'][
                'ModuleDirectory'] = "/invalid/path"
            helpers.default_config['Jouled']['StreamDirectory'] = temp
            with self.assertRaisesRegex(config.InvalidConfiguration, "ModuleDirectory"):
                config.load_configs(helpers.default_config)

            helpers.default_config['Jouled']['StreamDirectory'] = temp
            helpers.default_config['Jouled']['ModuleDirectory'] = temp

            # module doc file must be writable
            docfile = tempfile.NamedTemporaryFile()
            helpers.default_config['Jouled']['ModuleDocs'] = docfile.name
            os.chmod(docfile.name, 0o444)
            with self.assertRaisesRegex(config.InvalidConfiguration, "ModuleDocFile"):
                config.load_configs(helpers.default_config)

    def test_errors_on_invalid_procdb_settings(self):
        helpers.default_config['ProcDB'][
            'MaxLogLines'] = "-2"  # positive integers
        with self.assertRaisesRegex(config.InvalidConfiguration, "MaxLogLines"):
            config.load_configs(helpers.default_config, verify=False)

    def test_errors_on_invalid_nilmdb_settings(self):
        helpers.default_config['NilmDB'][
            'InsertionPeriod'] = "a"  # positive integers
        with self.assertRaisesRegex(config.InvalidConfiguration, "InsertionPeriod"):
            config.load_configs(helpers.default_config, verify=False)

        helpers.default_config['NilmDB'][
            'InsertionPeriod'] = "-2"  # positive integers
        with self.assertRaisesRegex(config.InvalidConfiguration, "InsertionPeriod"):
            config.load_configs(helpers.default_config, verify=False)
