from click.testing import CliRunner
import os
from aiohttp.test_utils import unused_port
import warnings
import json
import copy
import asyncio
import numpy as np

from tests import helpers

from joule.models import DataStream, Element, StreamInfo, pipes
from ..fake_joule import FakeJoule, FakeJouleTestCase
from joule.cli import main

warnings.simplefilter('always')


class TestDataIntervals(FakeJouleTestCase):

    def test_shows_all_data_intervals(self):
        server = FakeJoule()
        intervals = create_source_data(server)
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['data', 'intervals',
                                      '--start', '1 hour ago', '--end','now',
                                      '/test/source'])

        self.assertEqual(result.exit_code, 0)
        # make sure the intervals are displayed (one per line)
        output = result.output.split('\n')
        num_intervals = 0
        for line in output[1:]:
            if '[' in line:
                self.assertIn('Thu, 24 Jan', line)
                num_intervals+=1
        self.assertEqual(num_intervals, len(intervals))
        self.stop_server()

    def test_handles_no_intervals(self):
        server = FakeJoule()
        create_source_data(server, no_intervals=True)
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['data', 'intervals',
                                      '--start', '1 hour ago', '--end', 'now',
                                      '/test/source'])
        self.assertEqual(result.exit_code, 0)
        # make sure the intervals are displayed (one per line)
        output = result.output.split('\n')
        for line in output[1:]:
            self.assertNotIn('[', line)

        self.stop_server()

    def test_when_stream_does_not_exist(self):
        server = FakeJoule()
        server.response = "stream does not exist"
        server.http_code = 404
        server.stub_data_intervals = True
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['data', 'intervals', '/bad/path'])
        self.assertTrue("Error" in result.output)
        self.stop_server()

    def test_when_server_returns_invalid_data(self):
        server = FakeJoule()
        server.response = "notjson"
        server.stub_data_intervals = True
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['data', 'intervals', 'folder/stream'])
        self.assertTrue('Error' in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()

    def test_when_server_returns_error_code(self):
        server = FakeJoule()
        server.response = "test error"
        server.http_code = 500
        server.stub_data_intervals = True
        self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['data', 'intervals', 'folder/stream'])
        self.assertTrue('500' in result.output)
        self.assertTrue("test error" in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()


def create_source_data(server, no_intervals=False):
    # create the source stream
    src = DataStream(id=0, name="source", keep_us=100, datatype=DataStream.DATATYPE.FLOAT32)
    src.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in range(3)]

    # source has 100 rows of data in four intervals between [0, 100]
    src_data = helpers.create_data(src.layout, length=100, start=1548353881*1e6, step=1e6)

    ts = src_data['timestamp']

    if no_intervals:
        intervals = []
        src_info = StreamInfo(None, None, 0)

    else:
        intervals = [[ts[0], ts[24]],
                     [ts[25], ts[49]],
                     [ts[50], ts[74]],
                     [ts[75], ts[99]]]
        src_info = StreamInfo(intervals[0][0], intervals[-1][1], len(src_data))

    server.add_stream('/test/source', src, src_info, src_data, intervals)
    return intervals
