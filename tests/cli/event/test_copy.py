from click.testing import CliRunner
import os
import warnings
import re

from ..fake_joule import FakeJoule, FakeJouleTestCase
from joule.cli import main

EVENT_INFO = os.path.join(os.path.dirname(__file__), 'event_info.json')
EMPTY_EVENT_INFO = os.path.join(os.path.dirname(__file__), 'empty_event_info.json')

warnings.simplefilter('always')


class TestEventCopy(FakeJouleTestCase):

    def test_copies_all_data_to_new_stream(self):
        pass

    def test_copies_region_of_data(self):
        pass

    def test_replaces_existing_data_on_copy(self):
        pass

    def test_ignores_existing_data_on_copy(self):
        pass

    def test_errors_on_invalid_stream(self):
        pass

    def test_errors_when_source_is_empty(self):
        pass