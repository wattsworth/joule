import unittest

from joule.models import element
from joule.models.element import Element
from tests import helpers


class TestElement(unittest.TestCase):

    def setUp(self):
        config = helpers.parse_configs(
            """[Element1]
                 name = test
                 plottable = no
                 # None uses the default value
                 offset = None
                 default_min = -10.5
            """)
        self.base_config = config['Element1']

    def test_parses_base_config(self):
        e = element.from_config(self.base_config)
        self.assertEqual(e.name, "test")
        self.assertEqual(e.plottable, False)
        self.assertEqual(e.display_type, Element.DISPLAYTYPE.CONTINUOUS)  # default value
        self.assertEqual(e.offset, 0.0) # default value
        self.assertEqual(e.scale_factor, 1.0)  # default value
        self.assertEqual(e.default_min, -10.5)