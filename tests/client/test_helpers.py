import unittest
from joule import utilities


class TestNilmdbStore(unittest.TestCase):

    def test_yesno(self):
        self.assertTrue(utilities.yesno("yes"))
        self.assertFalse(utilities.yesno("no"))
        for val in ["badval", "", None]:
            with self.assertRaises(ValueError):
                utilities.yesno(val)
