import unittest

from joule.utilities import time


class TestTimeUtilities(unittest.TestCase):

    def test_time_helpers(self):
        now = time.time_now()
        time_str = time.timestamp_to_human(now)
        # make sure it doesn't raise any errors
        self.assertTrue(len(time_str) > 0)
        # check special timestamps
        self.assertEqual("(minimum)", time.timestamp_to_human(time.min_timestamp))
        self.assertEqual("(maximum)", time.timestamp_to_human(time.max_timestamp))
        # check conversion functions
        unix_now = time.timestamp_to_unix(now)
        self.assertEqual(now, time.unix_to_timestamp(unix_now))