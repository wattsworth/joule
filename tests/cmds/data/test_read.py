import unittest
from click.testing import CliRunner
import os
import signal
import multiprocessing
from aiohttp.test_utils import unused_port
import warnings
import time
import numpy as np

from ..fake_joule import FakeJoule, FakeJouleTestCase
from joule.cli import main
from joule.models import Stream, Element, StreamInfo, pipes
from tests import helpers

warnings.simplefilter('always')


class TestDataRead(FakeJouleTestCase):

    def test_reads_data(self):
        server = FakeJoule()
        # create the source stream
        src = Stream(id=0, name="source", keep_us=100, datatype=Stream.DATATYPE.FLOAT32)
        src.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in range(3)]
        # source has 100 rows of data between [0, 100]
        src_data = helpers.create_data(src.layout)
        src_info = StreamInfo(int(src_data['timestamp'][0]), int(src_data['timestamp'][-1]), len(src_data))
        server.add_stream('/test/source', src, src_info, src_data)

        url = self.start_server(server)
        runner = CliRunner()
        # add in some extra parameters to make sure they are parsed
        result = runner.invoke(main, ['--url', url, 'data', 'read', '/test/source',
                                      '--start', '0', '--end', '1 hour ago', '--max-rows', '1000'])
        self.assertEqual(result.exit_code, 0)
        output = result.output.split('\n')
        for x in range(len(src_data)):
            row = src_data[x]
            expected = "%d %s" % (row['timestamp'], ' '.join('%f' % x for x in row['data']))
            self.assertTrue(expected in output[x])
        self.stop_server()

    def test_reads_decimated_data(self):
        server = FakeJoule()
        # create the source stream
        src = Stream(id=0, name="source", keep_us=100, datatype=Stream.DATATYPE.FLOAT32)
        src.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in range(3)]
        # source has 200 rows of data between [0, 200] in two intervals
        src_data = np.hstack((helpers.create_data(src.decimated_layout, start=0, length=100, step=1),
                              pipes.interval_token(src.decimated_layout),
                              helpers.create_data(src.decimated_layout, start=100, length=100, step=1)))

        src_info = StreamInfo(int(src_data['timestamp'][0]), int(src_data['timestamp'][-1]), len(src_data))
        server.add_stream('/test/source', src, src_info, src_data)
        url = self.start_server(server)

        # mark the intervals and show the bounds
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'data', 'read', '/test/source',
                                      '--decimation-level', '16', '--mark-intervals',
                                      '--show-bounds'])
        self.assertEqual(result.exit_code, 0)
        output = result.output.split('\n')
        for x in range(len(src_data)):
            row = src_data[x]
            if row == pipes.interval_token(src.decimated_layout):
                expected = '# interval break'
            else:
                expected = "%d %s" % (row['timestamp'], ' '.join('%f' % x for x in row['data']))
            self.assertTrue(expected in output[x])

        # do not mark the intervals and hide the bounds
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'data', 'read', '/test/source',
                                      '--decimation-level', '16'])
        self.assertEqual(result.exit_code, 0)
        output = result.output.split('\n')
        offset = 0
        for x in range(len(src_data)):
            row = src_data[x]
            if row == pipes.interval_token(src.decimated_layout):
                offset = 1
                continue
            else:
                expected = "%d %s" % (row['timestamp'], ' '.join('%f' % x for x in row['data'][:3]))
            self.assertTrue(expected in output[x - offset])

        self.stop_server()

    def test_when_server_is_not_available(self):
        url = "http://127.0.0.1:%d" % unused_port()
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'data', 'read', '/test/source'])
        self.assertTrue('Error' in result.output)
        # self.assertEqual(result.exit_code, 1)

    def test_when_server_returns_error_code(self):
        server = FakeJoule()
        server.response = "test error"
        server.http_code = 500
        server.stub_data_read = True
        url = self.start_server(server)
        runner = CliRunner()
        result = runner.invoke(main, ['--url', url, 'data', 'read', '/test/source'])
        self.assertTrue('%d' % 500 in result.output)
        self.assertTrue("test error" in result.output)
        self.assertEqual(result.exit_code, 1)
        self.stop_server()

    def test_handles_bad_parameters(self):
        runner = CliRunner()
        result = runner.invoke(main, ['--url', 'none', 'data', 'read', '/test/source', '--start', 'invalid'])
        self.assertIn('start time', result.output)
        self.assertEqual(result.exit_code, 1)
        result = runner.invoke(main, ['--url', 'none', 'data', 'read', '/test/source', '--end', 'invalid'])
        self.assertIn('end time', result.output)
        self.assertEqual(result.exit_code, 1)