from click.testing import CliRunner
import os
import warnings
import json
import copy
import asyncio
import re
from unittest import SkipTest

from joule.models import DataStream
from ..fake_joule import FakeJoule, FakeJouleTestCase
from joule.cli import main

EVENT_INFO = os.path.join(os.path.dirname(__file__), 'event_info.json')
warnings.simplefilter('always')


class TestEventInfo(FakeJouleTestCase):

    def test_show_info(self):
        server = FakeJoule()
        with open(EVENT_INFO, 'r') as f:
            server.response = f.read()
        server.stub_event_info = True  # use the response text
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['event', 'info', '-e', '/folder_1/random'])
        self.assertEqual(result.exit_code, 0)
        # make sure the items are populated correctly

        self.stop_server()
