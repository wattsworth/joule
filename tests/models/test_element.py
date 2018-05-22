from joule.models import element
from joule.models.element import Element

from tests import helpers
import unittest


class TestElement(unittest.TestCase):

    def setUp(self):
        config = helpers.parse_configs(
            """[Element1]
                 name = test
                 plottable = no
                 offset = 5.2
            """)
        self.base_config = config['Element1']

    def test_parses_base_config(self):
        e = element.from_config(self.base_config)
        self.assertEqual(e.name, "test")
        self.assertEqual(e.plottable, False)
        self.assertEqual(e.display_type, Element.DISPLAYTYPE.CONTINUOUS)  # default value
        self.assertEqual(e.offset, 5.2)
        self.assertEqual(e.scale_factor, 1.0)  # default value
