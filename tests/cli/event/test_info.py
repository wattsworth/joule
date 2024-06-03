from click.testing import CliRunner
import os
import warnings
import re

from ..fake_joule import FakeJoule, FakeJouleTestCase
from joule.cli import main

EVENT_INFO = os.path.join(os.path.dirname(__file__), 'event_info.json')
EMPTY_EVENT_INFO = os.path.join(os.path.dirname(__file__), 'empty_event_info.json')

warnings.simplefilter('always')


class TestEventInfo(FakeJouleTestCase):

    def test_show_info(self):
        server = FakeJoule()
        with open(EVENT_INFO, 'r') as f:
            server.response = f.read()
        server.stub_event_info = True  # use the response text
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['event', 'info', '/folder_1/random'])
        self.assertCliSuccess(result)
        self.assertEqual(result.exit_code, 0)
        # make sure the items are populated correctly
        output = result.output.split('\n')
        row_line = [x for x in output if 'Events' in x][0]
        self.assertTrue("282587" in row_line)
        start_line = [x for x in output if 'Start' in x][0]

        # note: day and hour depends on client's timezone (check year and MM:SS)
        self.assertIsNotNone(re.search(r'2013-03-', start_line))
        end_line = [x for x in output if 'End' in x][0]
        self.assertIsNotNone(re.search(r'28:49', end_line))

        # make sure the event fields are present
        for field in ["type", "phase"]:
            line = [x for x in output if field in x][0]
            self.assertTrue("string" in line)
        for field in ['duration', 'isolated', 'position',
                      'real_power', 'power_factor', 'apparent_power',
                      'reactive_power', 'relative_variance']:
            line = [x for x in output if field in x][0]
            self.assertTrue("numeric" in line)
        self.stop_server()

    def test_shows_empty_info(self):
        server = FakeJoule()
        with open(EMPTY_EVENT_INFO, 'r') as f:
            server.response = f.read()
        server.stub_event_info = True  # use the response text
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['event', 'info', '/folder_1/random'])
        self.assertCliSuccess(result)
        self.assertEqual(result.exit_code, 0)
        # make sure the items are populated correctly
        output = result.output.split('\n')
        row_line = [x for x in output if 'Events' in x][0]
        self.assertTrue("0" in row_line)
        start_line = [x for x in output if 'Start' in x][0]

        # no time bounds
        self.assertTrue(u"\u2014" in start_line)
        end_line = [x for x in output if 'End' in x][0]
        self.assertTrue(u"\u2014" in end_line)

        # no event fields printed
        self.assertTrue("no fields specified" in result.output)
        self.stop_server()

    def test_errors_on_invalid_path(self):
        server = FakeJoule()
        server.response = "stream does not exist"
        server.http_code = 404
        server.stub_stream_info = True
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['event', 'info', '/bad/path'])
        self.assertTrue("Error" in result.output)
        self.stop_server()

