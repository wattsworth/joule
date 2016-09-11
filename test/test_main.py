from joule import main as basic

import unittest


class BasicTest(unittest.TestCase):
    def test_output(self):
        basic.main()
        self.assertEqual('foo'.upper(), 'FOO')
