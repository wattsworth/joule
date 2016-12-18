from joule import main as basic

import unittest


class TestConfigParsing(unittest.TestCase):

    def it_should_load_default_configs(self):
        main.run()
        main.config_file = defaults.config_dir

    def it_should_accept_custom_configs(self):
        main.run("--config /tmp/test")
        main.config_file = "/tmp/test"
