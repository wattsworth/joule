import unittest

from joule.utilities import misc


class TestMiscUtilities(unittest.TestCase):

    def test_yesno(self):
        self.assertTrue(misc.yesno("yes"))
        self.assertFalse(misc.yesno("no"))
        for val in ["badval", "", None]:
            with self.assertRaises(ValueError):
                misc.yesno(val)
