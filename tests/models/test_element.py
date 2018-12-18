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
        self.assertEqual(e.offset, 0.0)  # default value
        self.assertEqual(e.scale_factor, 1.0)  # default value
        self.assertEqual(e.default_min, -10.5)

    def test_updates(self):
        e = Element(name="test",
                    units="W",
                    plottable=True,
                    offset=0,
                    scale_factor=1,
                    display_type=Element.DISPLAYTYPE.EVENT,
                    default_min=None,
                    default_max=None)
        e.update_attributes({
            "name": "new name",
            "units": "nW",
            "plottable": False,
            "offset": -1,
            "scale_factor": 10,
            "display_type": "discrete",
            "default_min": 8,
            "default_max": 100
        })
        self.assertEqual("new name", e.name)
        self.assertEqual("nW", e.units)
        self.assertFalse(e.plottable)
        self.assertEqual(-1, e.offset)
        self.assertEqual(10, e.scale_factor)
        self.assertEqual(Element.DISPLAYTYPE.DISCRETE, e.display_type)
        self.assertEqual(8, e.default_min)
        self.assertEqual(100, e.default_max)
