import unittest

from joule import utilities

class TestUtilities(unittest.TestCase):

    def test_time_helpers(self):
        now = utilities.time_now()
        str = utilities.timestamp_to_human(now)
        # make sure it doesn't raise any errors
        self.assertTrue(len(str) > 0)
        # check special timestamps
        self.assertEqual("(minimum)", utilities.timestamp_to_human(utilities.min_timestamp))
        self.assertEqual("(maximum)", utilities.timestamp_to_human(utilities.max_timestamp))
        # check conversion functions
        unix_now = utilities.timestamp_to_unix(now)
        self.assertEqual(now, utilities.unix_to_timestamp(unix_now))

    def test_yesno(self):
        self.assertTrue(utilities.yesno("yes"))
        self.assertFalse(utilities.yesno("no"))
        for val in ["badval", "", None]:
            with self.assertRaises(ValueError):
                utilities.yesno(val)