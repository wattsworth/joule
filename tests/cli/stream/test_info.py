from click.testing import CliRunner
import os
import warnings
import json
import copy
import asyncio
import re

from joule.models import DataStream
from ..fake_joule import FakeJoule, FakeJouleTestCase
from joule.cli import main

STREAM_INFO = os.path.join(os.path.dirname(__file__), 'stream.json')
warnings.simplefilter('always')


class TestStreamInfo(FakeJouleTestCase):

    def test_shows_extended_stream_info(self):
        server = FakeJoule()
        with open(STREAM_INFO, 'r') as f:
            server.response = f.read()
        server.stub_stream_info = True  # use the response text
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['stream', 'info', '-e', '/folder_1/random'])
        self.assertEqual(result.exit_code, 0)
        # make sure the items are populated correctly
        output = result.output.split('\n')
        row_line = [x for x in output if 'Rows' in x][0]
        self.assertTrue("73820" in row_line)
        start_line = [x for x in output if 'Start' in x][0]

        # note: hour depends on client's timezone

        self.assertIsNotNone(re.search(r'2018-07-11 \d\d:50:44',
                                       start_line))
        end_line = [x for x in output if 'End' in x][0]
        self.assertIsNotNone(re.search(r'2018-07-25 \d\d:52:56',
                                       end_line))
        for element_name in ['x', 'y', 'z']:
            for line in output:
                if element_name in line:
                    break
            else:
                self.fail("element name %s not in output" % element_name)
        self.stop_server()

    def test_shows_basic_stream_info(self):
        server = FakeJoule()
        with open(STREAM_INFO, 'r') as f:
            server.response = f.read()
        server.stub_stream_info = True  # use the response text
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['stream', 'info', '/folder_1/random'])
        self.assertEqual(result.exit_code, 0)
        # make sure the items are populated correctly
        output = result.output.split('\n')
        row_line = [x for x in output if 'Rows' in x][0]
        self.assertTrue("73820" in row_line)
        start_line = [x for x in output if 'Start' in x][0]

        # note: hour depends on client's timezone

        self.assertIsNotNone(re.search(r'2018-07-11 \d\d:50:44',
                                       start_line))
        end_line = [x for x in output if 'End' in x][0]
        self.assertIsNotNone(re.search(r'2018-07-25 \d\d:52:56',
                                       end_line))
        # no table of rows
        for line in output:
            if 'Min,Max' in line:
                self.fail("it looks like the elements are still included in the display")
        self.stop_server()

    def test_handles_different_stream_configurations(self):
        server = FakeJoule()
        with open(STREAM_INFO, 'r') as f:
            orig_stream_data = json.loads(f.read())
        stream1 = copy.deepcopy(orig_stream_data)
        stream1['decimate'] = False
        # stream1 is configured but not active
        stream1['is_source'] = False
        stream1['is_destination'] = False
        stream1['is_configured'] = True
        stream1['keep_us'] = 8*60*60*1e6  # 8 hours
        stream2 = copy.deepcopy(orig_stream_data)
        stream2['keep_us'] = DataStream.KEEP_NONE
        stream2['description'] = 'description'
        stream2['data_info']['start'] = None
        stream2['data_info']['end'] = None
        # stream2 is idle
        stream2['is_source'] = False
        stream2['is_destination'] = False
        stream2['is_configured'] = False
        for stream in [stream1, stream2]:


            server.stub_stream_info = True  # use the response text
            server.response = json.dumps(stream)
            self.start_server(server)
            runner = CliRunner()
            result = runner.invoke(main, ['stream', 'info', '/folder_1/random'])
            # just make sure different configurations do not cause errors in the output
            self.assertEqual(result.exit_code, 0)
            self.stop_server()

    def test_when_stream_does_not_exist(self):
        server = FakeJoule()
        server.response = "stream does not exist"
        server.http_code = 404
        server.stub_stream_info = True
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, [ 'stream', 'info', '/bad/path'])
        self.assertTrue("Error" in result.output)
        self.stop_server()

    def test_when_server_returns_invalid_data(self):
        server = FakeJoule()
        server.response = "notjson"
        server.stub_stream_info = True
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['stream', 'info', 'folder/stream'])
        self.assertTrue('Error' in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()

    def test_when_server_returns_error_code(self):
        server = FakeJoule()
        server.response = "test error"
        server.http_code = 500
        server.stub_stream_info = True
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['stream', 'info', 'folder/stream'])
        self.assertTrue('500' in result.output)
        self.assertTrue("test error" in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()
