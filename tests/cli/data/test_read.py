from click.testing import CliRunner

import warnings
import numpy as np
import logging
import asyncio
import tempfile
import h5py
import unittest
import datetime

from ..fake_joule import FakeJoule, FakeJouleTestCase
from joule.cli import main
from joule.models import DataStream, Element, StreamInfo, pipes
from tests import helpers

warnings.simplefilter('always')
log = logging.getLogger('aiohttp.access')
log.setLevel(logging.WARNING)


class TestDataRead(FakeJouleTestCase):

    def test_reads_data(self):
        server = FakeJoule()
        # create the source stream
        src = DataStream(id=0, name="source", keep_us=100,
                         datatype=DataStream.DATATYPE.FLOAT32,
                         updated_at=datetime.datetime.utcnow())
        src.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in range(3)]
        # source has 100 rows of data between [0, 100]
        src_data = helpers.create_data(src.layout)
        src_info = StreamInfo(int(src_data['timestamp'][0]), int(src_data['timestamp'][-1]), len(src_data))
        server.add_stream('/test/source', src, src_info, src_data)

        self.start_server(server)
        runner = CliRunner()
        # add in some extra parameters to make sure they are parsed
        result = runner.invoke(main, ['data', 'read', '/test/source',
                                      '--start', '0', '--end', '1 hour ago'])
        _print_result_on_error(result)
        self.assertEqual(result.exit_code, 0)
        output = result.output.split('\n')
        for x in range(len(src_data)):
            row = src_data[x]
            expected = "%d %s" % (row['timestamp'], ' '.join('%f' % x for x in row['data']))
            self.assertTrue(expected in output[x + 1])

        self.stop_server()

    def test_reads_decimated_data(self):

        server = FakeJoule()
        # create the source stream
        src = DataStream(id=0, name="source", keep_us=100, datatype=DataStream.DATATYPE.FLOAT32,
                         updated_at=datetime.datetime.utcnow())
        src.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in range(3)]
        # source has 200 rows of data between [0, 200] in two intervals
        src_data = np.hstack((helpers.create_data(src.decimated_layout, start=0, length=100, step=1),
                              pipes.interval_token(src.decimated_layout),
                              helpers.create_data(src.decimated_layout, start=100, length=100, step=1)))

        src_info = StreamInfo(int(src_data['timestamp'][0]), int(src_data['timestamp'][-1]), len(src_data))
        server.add_stream('/test/source', src, src_info, src_data)
        self.start_server(server)

        # mark the intervals and show the bounds
        runner = CliRunner()
        result = runner.invoke(main, ['data', 'read', '/test/source',
                                      '--start', '0', '--end', '1 hour ago',
                                      '--max-rows', '28', '--mark-intervals',
                                      '--show-bounds'])
        _print_result_on_error(result)
        self.assertEqual(result.exit_code, 0)
        output = result.output.split('\n')
        for x in range(len(src_data)):
            row = src_data[x]
            if row == pipes.interval_token(src.decimated_layout):
                expected = '# interval break'
            else:
                expected = "%d %s" % (row['timestamp'], ' '.join('%f' % x for x in row['data']))
            # import pdb; pdb.set_trace()
            self.assertTrue(expected in output[x + 1],msg=f"{output[x+2]}!={expected}")


        # do not mark the intervals and hide the bounds
        runner = CliRunner()

        result = runner.invoke(main, ['data', 'read', '/test/source',
                                      '--start', '0', '--end', '1 hour ago',
                                      '--max-rows', '28'])
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
            self.assertTrue(expected in output[x - offset + 1])

        self.stop_server()

    def test_reads_selected_elements_of_decimated_data(self):
        server = FakeJoule()
        # create the source stream
        src = DataStream(id=0, name="source", keep_us=100, datatype=DataStream.DATATYPE.FLOAT32,
                         updated_at=datetime.datetime.utcnow())
        src.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in range(3)]
        # source has 200 rows of data between [0, 200] in two intervals
        src_data = np.hstack((helpers.create_data(src.decimated_layout, start=0, length=100, step=1),
                              pipes.interval_token(src.decimated_layout),
                              helpers.create_data(src.decimated_layout, start=100, length=100, step=1)))

        src_info = StreamInfo(int(src_data['timestamp'][0]), int(src_data['timestamp'][-1]), len(src_data))
        server.add_stream('/test/source', src, src_info, src_data)
        self.start_server(server)

        # mark the intervals and show the bounds
        runner = CliRunner()
        result = runner.invoke(main, ['data', 'read', '/test/source',
                                      '--start', '0', '--end', '1 hour ago',
                                      '--max-rows', '28', '--mark-intervals',
                                      '--show-bounds', '-i', '0,2'])
        _print_result_on_error(result)
        self.assertEqual(result.exit_code, 0)
        output = result.output.split('\n')
        for x in range(len(src_data)):
            row = src_data[x]
            if row == pipes.interval_token(src.decimated_layout):
                expected = '# interval break'
            else:
                data = row['data'][[0, 2, 3, 5, 6, 8]]
                expected = "%d %s" % (row['timestamp'], ' '.join('%f' % x for x in data))
            self.assertTrue(expected in output[x + 1])

        # do not mark the intervals and hide the bounds
        runner = CliRunner()

        result = runner.invoke(main, ['data', 'read', '/test/source',
                                      '--start', '0', '--end', '1 hour ago',
                                      '--max-rows', '28'])
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
            self.assertTrue(expected in output[x - offset + 1])

        self.stop_server()

    def test_reads_selected_elements(self):
        server = FakeJoule()
        # create the source stream
        src = DataStream(id=0, name="source", keep_us=100, datatype=DataStream.DATATYPE.FLOAT32,
                         updated_at=datetime.datetime.utcnow())
        src.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in range(3)]
        # source has 100 rows of data between [0, 100]
        src_data = helpers.create_data(src.layout)
        src_info = StreamInfo(int(src_data['timestamp'][0]), int(src_data['timestamp'][-1]), len(src_data))
        server.add_stream('/test/source', src, src_info, src_data)

        self.start_server(server)
        runner = CliRunner()
        # add in some extra parameters to make sure they are parsed
        result = runner.invoke(main, ['data', 'read', '/test/source', '-i', '1,0',
                                      '--start', '0', '--end', '1 hour ago'])
        _print_result_on_error(result)
        self.assertEqual(result.exit_code, 0)
        output = result.output.split('\n')
        for x in range(len(src_data)):
            row = src_data[x]
            expected = "%d %s" % (row['timestamp'], ' '.join('%f' % x for x in row['data'][[1, 0]]))
            self.assertTrue(expected in output[x + 1])

        self.stop_server()

    def test_reads_selected_elements_to_file(self):
        server = FakeJoule()
        # create the source stream
        src = DataStream(id=0, name="source", keep_us=100, datatype=DataStream.DATATYPE.UINT16,
                         updated_at=datetime.datetime.utcnow())
        src.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in range(3)]
        # source has 100 rows of data between [0, 100]
        src_data = helpers.create_data(src.layout)
        src_info = StreamInfo(int(src_data['timestamp'][0]), int(src_data['timestamp'][-1]), len(src_data))
        server.add_stream('/test/source', src, src_info, src_data)

        self.start_server(server)
        runner = CliRunner()
        # add in some extra parameters to make sure they are parsed
        with tempfile.NamedTemporaryFile() as data_file:
            result = runner.invoke(main, ['data', 'read', '/test/source',
                                          '--start', '0', '--end', '1 hour ago',
                                          '-i', '0,2',
                                          '--file', data_file.name])

            _print_result_on_error(result)
            self.assertEqual(result.exit_code, 0)
            h5_file = h5py.File(data_file.name, 'r')
            self.assertEqual(src_data['data'].dtype, h5_file['data'].dtype)
            self.assertEqual(h5_file['timestamp'].dtype, np.dtype('i8'))

            np.testing.assert_array_almost_equal(h5_file['data'], src_data['data'][:, [0, 2]])
            np.testing.assert_array_almost_equal(h5_file['timestamp'], src_data['timestamp'][:, None])

            h5_file.close()

        self.stop_server()

    def test_reads_data_to_file(self):
        server = FakeJoule()
        # create the source stream
        src = DataStream(id=0, name="source", keep_us=100, datatype=DataStream.DATATYPE.FLOAT32,
                         updated_at=datetime.datetime.utcnow())
        src.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in range(3)]
        # source has 100 rows of data between [0, 100]
        src_data = helpers.create_data(src.layout)
        src_info = StreamInfo(int(src_data['timestamp'][0]), int(src_data['timestamp'][-1]), len(src_data))
        server.add_stream('/test/source', src, src_info, src_data)

        self.start_server(server)
        runner = CliRunner()
        # add in some extra parameters to make sure they are parsed
        with tempfile.NamedTemporaryFile() as data_file:
            result = runner.invoke(main, ['data', 'read', '/test/source',
                                          '--start', '0', '--end', '1 hour ago',
                                          '--file', data_file.name])

            _print_result_on_error(result)
            self.assertEqual(result.exit_code, 0)
            h5_file = h5py.File(data_file.name, 'r')
            np.testing.assert_array_almost_equal(src_data['timestamp'][:, None], h5_file['timestamp'])
            np.testing.assert_array_equal(src_data['data'], h5_file['data'])

            h5_file.close()

        self.stop_server()

    def test_when_server_returns_error_code(self):
        server = FakeJoule()
        # create the source stream
        src = DataStream(id=0, name="source", keep_us=100, datatype=DataStream.DATATYPE.FLOAT32,
                         updated_at=datetime.datetime.utcnow())
        src.elements = [Element(name="e%d" % x, index=x, display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in range(3)]
        # source has 200 rows of data between [0, 200] in two intervals
        src_data = np.hstack((helpers.create_data(src.decimated_layout, start=0, length=100, step=1),
                              pipes.interval_token(src.decimated_layout),
                              helpers.create_data(src.decimated_layout, start=100, length=100, step=1)))

        src_info = StreamInfo(int(src_data['timestamp'][0]), int(src_data['timestamp'][-1]), len(src_data))
        server.add_stream('/test/source', src, src_info, src_data)

        server.response = "test error"
        server.http_code = 500
        server.stub_data_read = True
        self.start_server(server)
        runner = CliRunner()

        with self.assertLogs(level=logging.ERROR):
            runner.invoke(main, ['data', 'read', '/test/source', '--start', 'now'])

        self.stop_server()

    def test_handles_bad_parameters(self):
        runner = CliRunner()
        result = runner.invoke(main, ['data', 'read', '/test/source', '--start', 'invalid'])
        self.assertIn('start time', result.output)
        self.assertEqual(result.exit_code, 1)
        result = runner.invoke(main, ['data', 'read', '/test/source', '--end', 'invalid'])
        self.assertIn('end time', result.output)
        self.assertEqual(result.exit_code, 1)


def _print_result_on_error(result):
    if result.exit_code != 0:
        print("output: ", result.output)
        print("exception: ", result.exception)
