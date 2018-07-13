import unittest

from joule.client import BaseModule


class TestBaseModule(unittest.TestCase):

    def test_can_create_base_module(self):
        module = BaseModule()
