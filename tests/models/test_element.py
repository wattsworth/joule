import unittest

from joule.models import element
from joule.models.element import Element, from_json
from tests import helpers
from joule.errors import ConfigurationError

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
        self.assertFalse(e.plottable)
        self.assertEqual(e.display_type, Element.DISPLAYTYPE.CONTINUOUS)  # default value
        self.assertEqual(e.offset, 0.0)  # default value
        self.assertEqual(e.scale_factor, 1.0)  # default value
        self.assertEqual(e.default_min, -10.5)

    def test_merges_config(self):
        e1 = Element(name="test",
                    units="W",
                    plottable=True,
                    offset=0,
                    scale_factor=1,
                    display_type=Element.DISPLAYTYPE.EVENT,
                    default_min=None,
                    default_max=None)
        e2 = from_json(e1.to_json())
        e1.index=1
        e2.index=1
        # nothing to merge
        self.assertFalse(e1.merge_configs(e2))
        # merges new configs
        e2.name='new name'
        self.assertTrue(e1.merge_configs(e2))
        self.assertEqual(e1.name, 'new name')
        self.assertEqual(e1.units, 'W')
        # cannot merge different indices
        e2.index=2
        with self.assertRaisesRegex(ConfigurationError, 'cannot merge'):
            e1.merge_configs(e2)

       

    def test_creates_default_display_type(self):
        e = Element(name="test",
                    units="W",
                    plottable=True,
                    offset=0,
                    scale_factor=1,
                    display_type=None,
                    default_min=None,
                    default_max=None)
        element_json = e.to_json()
        self.assertEqual('CONTINUOUS', element_json['display_type'])

    def test_equality(self):
        e1 = Element(name="test",
                     units="W",
                     plottable=True,
                     offset=0,
                     scale_factor=1,
                     display_type=Element.DISPLAYTYPE.EVENT,
                     default_min=None,
                     default_max=None)
        e2 = Element(name="test",
                     units="W",
                     plottable=True,
                     offset=0,
                     scale_factor=1,
                     display_type=Element.DISPLAYTYPE.EVENT,
                     default_min=None,
                     default_max=None)
        self.assertEqual(e1, e2)
        e2.name = "different"
        self.assertNotEqual(e1, e2)
        self.assertNotEqual(e1,'not equal')

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
