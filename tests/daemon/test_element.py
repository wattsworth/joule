import joule.daemon.element as stream

from tests import helpers
import unittest


class TestElement(unittest.TestCase):

    def setUp(self):
        self.parser = stream.Parser()
        config = helpers.parse_configs(
            """[Element1]
                 name = test
                 plottable = no
                 offset = 5.2
            """)
        self.base_config = config['Element1']

    def test_parses_base_config(self):
        stream = self.parser.run(self.base_config)
        self.assertEqual(stream.name, "test")
        self.assertEqual(stream.plottable, False)
        self.assertEqual(stream.discrete, False)  # default value
        self.assertEqual(stream.offset, 5.2)
        self.assertEqual(stream.scale_factor, 1.0)  # default value
